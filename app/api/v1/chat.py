from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.chat import ChatAnswerResponse, ChatMessageRead, ChatRequest, ChatSessionRead
from app.services.chat_service import ChatService, ChatSessionNotFoundError, get_chat_service
from app.services.kb_service import KnowledgeBaseNotFoundError

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/kbs/{kb_id}/chat", response_model=ChatAnswerResponse)
def chat(
    kb_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatAnswerResponse:
    try:
        answer = chat_service.ask(
            session,
            user_id=current_user.id,
            kb_id=kb_id,
            question=payload.question.strip(),
            session_id=payload.session_id,
        )
    except (KnowledgeBaseNotFoundError, ChatSessionNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ChatAnswerResponse(answer=answer.answer, references=answer.references, session_id=answer.session_id)


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
    try:
        messages = chat_service.list_messages(session, user_id=current_user.id, session_id=session_id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [ChatMessageRead.model_validate(message) for message in messages]
