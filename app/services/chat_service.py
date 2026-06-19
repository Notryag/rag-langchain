from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.chat import ChatMessage, ChatRole, ChatSession
from app.retrieval.pgvector_store import retrieve_pgvector_chunks
from app.services.hot_question_cache import (
    CachedChatAnswer,
    InMemoryHotQuestionCache,
    RedisHotQuestionCache,
    build_hot_question_cache_key,
    build_hot_question_scope_key,
    get_hot_question_cache,
)
from app.services.kb_service import KnowledgeBaseService


class ChatSessionNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    references: list[dict[str, Any]]
    session_id: int
    cache_hit: bool = False


class ChatService:
    def __init__(
        self,
        *,
        kb_service: KnowledgeBaseService | None = None,
        retriever=retrieve_pgvector_chunks,
        chat_model=None,
        answer_cache: RedisHotQuestionCache | InMemoryHotQuestionCache | None = None,
    ) -> None:
        self._kb_service = kb_service or KnowledgeBaseService()
        self._retriever = retriever
        self._chat_model = chat_model
        self._answer_cache = answer_cache

    def ask(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None = None,
    ) -> ChatAnswer:
        self._kb_service.get_for_user(session, user_id=user_id, kb_id=kb_id)
        chat_session = self._get_or_create_session(
            session,
            user_id=user_id,
            kb_id=kb_id,
            session_id=session_id,
            question=question,
        )
        user_message = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.USER,
            content=question,
            references=[],
        )
        session.add(user_message)
        session.commit()

        cache_key = build_hot_question_cache_key(user_id=user_id, kb_id=kb_id, question=question, top_k=settings.top_k)
        scope_key = build_hot_question_scope_key(user_id=user_id, kb_id=kb_id)
        cached_answer = self._get_cached_answer(cache_key=cache_key)
        if cached_answer is None:
            chunks = self._retriever(
                session,
                user_id=user_id,
                kb_id=kb_id,
                query=question,
                top_k=settings.top_k,
            )
            references = [chunk.to_reference() for chunk in chunks]
            answer = self._generate_answer(question=question, references=references)
            self._set_cached_answer(
                cache_key=cache_key,
                scope_key=scope_key,
                answer=answer,
                references=references,
            )
            cache_hit = False
        else:
            answer = cached_answer.answer
            references = cached_answer.references
            cache_hit = True

        assistant_message = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.ASSISTANT,
            content=answer,
            references=references,
        )
        session.add(assistant_message)
        session.commit()
        return ChatAnswer(answer=answer, references=references, session_id=chat_session.id, cache_hit=cache_hit)

    def list_sessions(self, session: Session, *, user_id: int) -> list[ChatSession]:
        statement = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
        return list(session.scalars(statement))

    def list_messages(self, session: Session, *, user_id: int, session_id: int) -> list[ChatMessage]:
        chat_session = self._get_session_for_user(session, user_id=user_id, session_id=session_id)
        statement = select(ChatMessage).where(ChatMessage.session_id == chat_session.id).order_by(ChatMessage.created_at)
        return list(session.scalars(statement))

    def _get_or_create_session(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        session_id: int | None,
        question: str,
    ) -> ChatSession:
        if session_id is not None:
            chat_session = self._get_session_for_user(session, user_id=user_id, session_id=session_id)
            if chat_session.kb_id != kb_id:
                raise ChatSessionNotFoundError("Chat session not found")
            return chat_session

        title = question.strip()[:60] or "新会话"
        chat_session = ChatSession(user_id=user_id, kb_id=kb_id, title=title)
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return chat_session

    def _get_session_for_user(self, session: Session, *, user_id: int, session_id: int) -> ChatSession:
        statement = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        chat_session = session.scalar(statement)
        if chat_session is None:
            raise ChatSessionNotFoundError("Chat session not found")
        return chat_session

    def _generate_answer(self, *, question: str, references: list[dict[str, Any]]) -> str:
        if not references:
            return "当前知识库中没有检索到足够相关的内容，无法基于资料回答。"

        context = "\n\n".join(
            f"[{index}] filename={reference['filename']}, chunk={reference['chunk_index']}\n{reference['content']}"
            for index, reference in enumerate(references, start=1)
        )
        model = self._chat_model or _build_chat_model()
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "你是企业知识库问答助手。必须仅根据给定资料回答；"
                        "资料不足时说明无法基于资料回答；回答要简洁，并提及相关引用编号。"
                    )
                ),
                HumanMessage(content=f"资料:\n{context}\n\n问题: {question}"),
            ]
        )
        return str(getattr(response, "content", response)).strip()

    def _get_cached_answer(self, *, cache_key: str) -> CachedChatAnswer | None:
        if not settings.hot_question_cache_enabled:
            return None
        return self._cache().get(key=cache_key)

    def _set_cached_answer(
        self,
        *,
        cache_key: str,
        scope_key: str,
        answer: str,
        references: list[dict[str, Any]],
    ) -> None:
        if not settings.hot_question_cache_enabled:
            return
        self._cache().set(
            key=cache_key,
            scope_key=scope_key,
            value=CachedChatAnswer(answer=answer, references=references),
            ttl_seconds=settings.hot_question_cache_ttl_seconds,
        )

    def _cache(self) -> RedisHotQuestionCache | InMemoryHotQuestionCache:
        return self._answer_cache or get_hot_question_cache()


def _build_chat_model() -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": settings.chat_model,
        "api_key": settings.openai_api_key,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


def get_chat_service() -> ChatService:
    return ChatService()
