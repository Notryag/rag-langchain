from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.chat import ChatAnswerResponse, ChatMessageRead, ChatRequest, ChatSessionRead
from app.services.chat_service import ChatService, get_chat_service
from app.services.operation_log_service import OperationLogService, get_operation_log_service

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _sse_payload(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _answer_chunks(answer: str, *, chunk_size: int = 32):
    for start in range(0, len(answer), chunk_size):
        yield answer[start : start + chunk_size]


@router.post("/kbs/{kb_id}/chat", response_model=ChatAnswerResponse)
def chat(
    kb_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    chat_service: ChatService = Depends(get_chat_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> ChatAnswerResponse:
    answer = chat_service.ask(
        session,
        user_id=current_user.id,
        kb_id=kb_id,
        question=payload.question.strip(),
        session_id=payload.session_id,
    )
    operation_log_service.record(
        session,
        user_id=current_user.id,
        action="chat.ask",
        resource_type="chat_session",
        resource_id=answer.session_id,
        details={"kb_id": kb_id, "reference_count": len(answer.references), "cache_hit": answer.cache_hit},
    )
    return ChatAnswerResponse(answer=answer.answer, references=answer.references, session_id=answer.session_id)


@router.post("/kbs/{kb_id}/chat/stream")
def chat_stream(
    kb_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    chat_service: ChatService = Depends(get_chat_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> StreamingResponse:
    def event_generator():
        answer = chat_service.ask(
            session,
            user_id=current_user.id,
            kb_id=kb_id,
            question=payload.question.strip(),
            session_id=payload.session_id,
        )
        operation_log_service.record(
            session,
            user_id=current_user.id,
            action="chat.stream",
            resource_type="chat_session",
            resource_id=answer.session_id,
            details={"kb_id": kb_id, "reference_count": len(answer.references), "cache_hit": answer.cache_hit},
        )
        streamed_answer = ""
        for content in _answer_chunks(answer.answer):
            streamed_answer += content
            yield _sse_payload("answer", {"content": content, "answer": streamed_answer})
        yield _sse_payload(
            "complete",
            {
                "answer": answer.answer,
                "references": answer.references,
                "session_id": answer.session_id,
                "cache_hit": answer.cache_hit,
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/chat-sessions", response_model=list[ChatSessionRead])
def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatSessionRead]:
    return [
        ChatSessionRead.model_validate(chat_session)
        for chat_session in chat_service.list_sessions(session, user_id=current_user.id)
    ]


@router.get("/chat-sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def list_chat_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatMessageRead]:
    messages = chat_service.list_messages(session, user_id=current_user.id, session_id=session_id)
    return [ChatMessageRead.model_validate(message) for message in messages]
