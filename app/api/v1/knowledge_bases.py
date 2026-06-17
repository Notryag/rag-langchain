from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseRead, KnowledgeBaseUpdate
from app.services.kb_service import KnowledgeBaseNotFoundError, KnowledgeBaseService, get_kb_service

router = APIRouter(prefix="/api/v1/kbs", tags=["knowledge_bases"])


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> KnowledgeBaseRead:
    knowledge_base = kb_service.create(session, user_id=current_user.id, payload=payload)
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> list[KnowledgeBaseRead]:
    return [KnowledgeBaseRead.model_validate(item) for item in kb_service.list_for_user(session, user_id=current_user.id)]


@router.get("/{kb_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> KnowledgeBaseRead:
    try:
        knowledge_base = kb_service.get_for_user(session, user_id=current_user.id, kb_id=kb_id)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.put("/{kb_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> KnowledgeBaseRead:
    try:
        knowledge_base = kb_service.update(session, user_id=current_user.id, kb_id=kb_id, payload=payload)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    kb_service: KnowledgeBaseService = Depends(get_kb_service),
) -> Response:
    try:
        kb_service.delete(session, user_id=current_user.id, kb_id=kb_id)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
