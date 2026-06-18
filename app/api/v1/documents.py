from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.document import DocumentProcessResponse, DocumentRead
from app.services.document_service import DocumentNotFoundError, DocumentService, get_document_service
from app.services.kb_service import KnowledgeBaseNotFoundError

router = APIRouter(tags=["documents"])


@router.post("/api/v1/kbs/{kb_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentRead:
    content = await file.read()
    try:
        document = document_service.create_upload(
            session,
            user_id=current_user.id,
            kb_id=kb_id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            content=content,
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentRead.model_validate(document)


@router.get("/api/v1/kbs/{kb_id}/documents", response_model=list[DocumentRead])
def list_documents(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> list[DocumentRead]:
    try:
        documents = document_service.list_for_kb(session, user_id=current_user.id, kb_id=kb_id)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DocumentRead.model_validate(document) for document in documents]


@router.get("/api/v1/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentRead:
    try:
        document = document_service.get_for_user(session, user_id=current_user.id, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentRead.model_validate(document)


@router.delete("/api/v1/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        document_service.delete(session, user_id=current_user.id, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/v1/documents/{document_id}/process", response_model=DocumentProcessResponse)
def process_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentProcessResponse:
    try:
        document, parsed_units = document_service.process_sync(
            session,
            user_id=current_user.id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return DocumentProcessResponse(document=DocumentRead.model_validate(document), parsed_units=parsed_units)
