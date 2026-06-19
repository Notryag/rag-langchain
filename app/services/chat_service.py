from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.chat import ChatMessage, ChatRole, ChatRun, ChatRunStatus, ChatSession
from app.retrieval.pgvector_store import retrieve_pgvector_retrieved_chunks
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
    run_id: int
    cache_hit: bool = False
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatStreamEvent:
    type: Literal["answer_delta", "complete", "error"]
    content: str = ""
    answer: str = ""
    result: ChatAnswer | None = None
    error_message: str | None = None


class ChatService:
    def __init__(
        self,
        *,
        kb_service: KnowledgeBaseService | None = None,
        retriever=retrieve_pgvector_retrieved_chunks,
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

        chat_run = self._create_run(
            session,
            user_id=user_id,
            kb_id=kb_id,
            chat_session_id=chat_session.id,
            question=question,
        )
        cache_key = build_hot_question_cache_key(user_id=user_id, kb_id=kb_id, question=question, top_k=settings.top_k)
        scope_key = build_hot_question_scope_key(user_id=user_id, kb_id=kb_id)
        try:
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
                answer, usage = self._generate_answer(question=question, references=references)
                self._set_cached_answer(
                    cache_key=cache_key,
                    scope_key=scope_key,
                    answer=answer,
                    references=references,
                    usage=usage,
                )
                cache_hit = False
            else:
                answer = cached_answer.answer
                references = cached_answer.references
                cache_hit = True
                usage = _cached_usage(cached_answer.usage)
        except Exception as exc:
            self._mark_run_failed(session, chat_run=chat_run, error_message=str(exc))
            raise

        assistant_message = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.ASSISTANT,
            content=answer,
            references=references,
        )
        session.add(assistant_message)
        self._mark_run_completed(
            session,
            chat_run=chat_run,
            answer=answer,
            references=references,
            usage=usage,
            cache_hit=cache_hit,
        )
        session.commit()
        return ChatAnswer(
            answer=answer,
            references=references,
            session_id=chat_session.id,
            run_id=chat_run.id,
            cache_hit=cache_hit,
            usage=usage,
        )

    def stream(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None = None,
    ) -> Iterator[ChatStreamEvent]:
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

        chat_run = self._create_run(
            session,
            user_id=user_id,
            kb_id=kb_id,
            chat_session_id=chat_session.id,
            question=question,
        )
        cache_key = build_hot_question_cache_key(user_id=user_id, kb_id=kb_id, question=question, top_k=settings.top_k)
        scope_key = build_hot_question_scope_key(user_id=user_id, kb_id=kb_id)

        try:
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
                answer_parts: list[str] = []
                usage: dict[str, Any] = _zero_usage(cached=False)
                for content, usage_update in self._stream_generate_answer(question=question, references=references):
                    if usage_update is not None:
                        usage = usage_update
                    if not content:
                        continue
                    answer_parts.append(content)
                    yield ChatStreamEvent(type="answer_delta", content=content, answer="".join(answer_parts))

                answer = "".join(answer_parts)
                self._set_cached_answer(
                    cache_key=cache_key,
                    scope_key=scope_key,
                    answer=answer,
                    references=references,
                    usage=usage,
                )
                cache_hit = False
            else:
                answer = cached_answer.answer
                references = cached_answer.references
                usage = _cached_usage(cached_answer.usage)
                cache_hit = True
                streamed_answer = ""
                for content in _answer_chunks(answer):
                    streamed_answer += content
                    yield ChatStreamEvent(type="answer_delta", content=content, answer=streamed_answer)

            assistant_message = ChatMessage(
                session_id=chat_session.id,
                role=ChatRole.ASSISTANT,
                content=answer,
                references=references,
            )
            session.add(assistant_message)
            self._mark_run_completed(
                session,
                chat_run=chat_run,
                answer=answer,
                references=references,
                usage=usage,
                cache_hit=cache_hit,
            )
            session.commit()
            result = ChatAnswer(
                answer=answer,
                references=references,
                session_id=chat_session.id,
                run_id=chat_run.id,
                cache_hit=cache_hit,
                usage=usage,
            )
            yield ChatStreamEvent(type="complete", answer=answer, result=result)
        except Exception as exc:
            self._mark_run_failed(session, chat_run=chat_run, error_message=str(exc))
            yield ChatStreamEvent(type="error", error_message=str(exc))
            return

    def _create_run(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        chat_session_id: int,
        question: str,
    ) -> ChatRun:
        chat_run = ChatRun(
            session_id=chat_session_id,
            user_id=user_id,
            kb_id=kb_id,
            status=ChatRunStatus.RUNNING,
            question=question,
            references=[],
            usage={},
            cache_hit=False,
        )
        session.add(chat_run)
        session.commit()
        session.refresh(chat_run)
        return chat_run

    def _mark_run_completed(
        self,
        session: Session,
        *,
        chat_run: ChatRun,
        answer: str,
        references: list[dict[str, Any]],
        usage: dict[str, Any],
        cache_hit: bool,
    ) -> None:
        chat_run.status = ChatRunStatus.COMPLETED
        chat_run.answer = answer
        chat_run.references = references
        chat_run.usage = usage
        chat_run.cache_hit = cache_hit
        chat_run.error_message = None

    def _mark_run_failed(self, session: Session, *, chat_run: ChatRun, error_message: str) -> None:
        chat_run.status = ChatRunStatus.FAILED
        chat_run.error_message = error_message
        session.commit()

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

    def _generate_answer(self, *, question: str, references: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        if not references:
            return "当前知识库中没有检索到足够相关的内容，无法基于资料回答。", _zero_usage(cached=False)

        context = _build_reference_context(references, max_context_chars=settings.retrieval_max_context_chars)
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
        return str(getattr(response, "content", response)).strip(), _extract_usage(response)

    def _stream_generate_answer(
        self,
        *,
        question: str,
        references: list[dict[str, Any]],
    ) -> Iterator[tuple[str, dict[str, Any] | None]]:
        if not references:
            yield "当前知识库中没有检索到足够相关的内容，无法基于资料回答。", _zero_usage(cached=False)
            return

        context = _build_reference_context(references, max_context_chars=settings.retrieval_max_context_chars)
        messages = [
            SystemMessage(
                content=(
                    "你是企业知识库问答助手。必须仅根据给定资料回答；"
                    "资料不足时说明无法基于资料回答；回答要简洁，并提及相关引用编号。"
                )
            ),
            HumanMessage(content=f"资料:\n{context}\n\n问题: {question}"),
        ]
        model = self._chat_model or _build_chat_model()
        stream = getattr(model, "stream", None)
        if stream is None:
            response = model.invoke(messages)
            yield str(getattr(response, "content", response)).strip(), _extract_usage(response)
            return

        usage = _zero_usage(cached=False)
        for chunk in stream(messages):
            usage = _merge_usage(usage, _extract_usage(chunk))
            yield str(getattr(chunk, "content", chunk)), None
        yield "", usage

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
        usage: dict[str, Any],
    ) -> None:
        if not settings.hot_question_cache_enabled:
            return
        self._cache().set(
            key=cache_key,
            scope_key=scope_key,
            value=CachedChatAnswer(answer=answer, references=references, usage=usage),
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


def _extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return dict(usage)

    response_metadata = getattr(response, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or response_metadata.get("usage")
    if token_usage:
        return dict(token_usage)

    return _zero_usage(cached=False)


def _zero_usage(*, cached: bool) -> dict[str, Any]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached": cached,
    }


def _cached_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(usage or _zero_usage(cached=False))
    payload["cached"] = True
    return payload


def _answer_chunks(answer: str, *, chunk_size: int = 32) -> Iterator[str]:
    for start in range(0, len(answer), chunk_size):
        yield answer[start : start + chunk_size]


def _build_reference_context(references: list[dict[str, Any]], *, max_context_chars: int) -> str:
    parts: list[str] = []
    consumed_chars = 0
    separator = "\n\n"
    for index, reference in enumerate(references, start=1):
        header = f"[{index}] filename={reference['filename']}, chunk={reference['chunk_index']}\n"
        remaining_chars = max_context_chars - consumed_chars - (len(separator) if parts else 0)
        if remaining_chars <= len(header):
            break

        content_budget = remaining_chars - len(header)
        content = str(reference.get("content", ""))
        if len(content) > content_budget:
            if content_budget <= 3:
                content = content[:content_budget]
            else:
                content = content[: content_budget - 3].rstrip() + "..."
        part = f"{header}{content}"
        parts.append(part)
        consumed_chars += len(part) + (len(separator) if len(parts) > 1 else 0)

    return separator.join(parts)


def _merge_usage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, int):
            merged[key] = int(merged.get(key, 0)) + value
        else:
            merged[key] = value
    merged["cached"] = False
    return merged


def get_chat_service() -> ChatService:
    return ChatService()
