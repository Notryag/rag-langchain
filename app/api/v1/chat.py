from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.runtime.schemas import DisconnectMode
from app.runtime.service import RuntimeService, get_runtime_service
from app.schemas.chat import (
    ChatAnswerResponse,
    ChatMessageRead,
    ChatRequest,
    ChatRunCancelResponse,
    ChatRunRead,
    ChatSessionRead,
)
from app.services.chat_service import ChatService, ChatSessionNotFoundError, get_chat_service
from app.services.operation_log_service import OperationLogService, get_operation_log_service

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _sse_payload(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
        resource_type="chat_run",
        resource_id=answer.run_id,
        details={
            "kb_id": kb_id,
            "session_id": answer.session_id,
            "reference_count": len(answer.references),
            "cache_hit": answer.cache_hit,
            "usage": answer.usage,
        },
    )
    return ChatAnswerResponse(
        answer=answer.answer,
        references=answer.references,
        session_id=answer.session_id,
        run_id=answer.run_id,
        usage=answer.usage,
    )


@router.post("/kbs/{kb_id}/chat/stream")
def chat_stream(
    kb_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    runtime_service: RuntimeService = Depends(get_runtime_service),
    operation_log_service: OperationLogService = Depends(get_operation_log_service),
) -> StreamingResponse:
    async def event_generator():
        record = await runtime_service.start_chat_run(
            session,
            user_id=current_user.id,
            kb_id=kb_id,
            question=payload.question.strip(),
            session_id=payload.session_id,
        )
        operation_log_service.record(
            session,
            user_id=current_user.id,
            action="chat.run.start",
            resource_type="chat_run",
            resource_id=record.run_id,
            details={"kb_id": kb_id, "session_id": record.session_id},
        )
        yield _sse_payload(
            "metadata",
            {
                "run_id": record.run_id,
                "session_id": record.session_id,
                "kb_id": record.kb_id,
            },
        )
        try:
            async for event in runtime_service.stream_run(record.run_id, disconnect_mode=DisconnectMode.CANCEL):
                if event.event == "heartbeat":
                    yield ": heartbeat\n\n"
                    continue
                if event.event == "end":
                    yield _sse_payload("end", {})
                    return

                if event.event == "complete":
                    payload_data = event.data if isinstance(event.data, dict) else {}
                    operation_log_service.record(
                        session,
                        user_id=current_user.id,
                        action="chat.stream",
                        resource_type="chat_run",
                        resource_id=record.run_id,
                        details={
                            "kb_id": kb_id,
                            "session_id": record.session_id,
                            "reference_count": len(payload_data.get("references") or []),
                            "cache_hit": payload_data.get("cache_hit", False),
                            "usage": payload_data.get("usage"),
                        },
                    )
                yield _sse_payload(event.event, event.data if isinstance(event.data, dict) else {"value": event.data})
        except Exception as exc:
            yield _sse_payload("error", {"message": str(exc)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/chat-runs/{run_id}", response_model=ChatRunRead)
def get_chat_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    runtime_service: RuntimeService = Depends(get_runtime_service),
) -> ChatRunRead:
    chat_run = runtime_service.get_run_for_user(session, run_id=run_id, user_id=current_user.id)
    if chat_run is None:
        raise ChatSessionNotFoundError("Chat run not found")
    return ChatRunRead.model_validate(chat_run)


@router.post("/chat-runs/{run_id}/cancel", response_model=ChatRunCancelResponse)
async def cancel_chat_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    runtime_service: RuntimeService = Depends(get_runtime_service),
) -> ChatRunCancelResponse:
    cancelled = await runtime_service.cancel_run(run_id, user_id=current_user.id)
    return ChatRunCancelResponse(run_id=run_id, cancelled=cancelled)


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
