from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.document import Document, DocumentStatus
from app.retrieval.parser import parse_document_file
from app.services.kb_service import KnowledgeBaseService


class DocumentNotFoundError(ValueError):
    pass


class DocumentService:
    def __init__(
        self,
        *,
        upload_dir: str = settings.upload_dir,
        kb_service: KnowledgeBaseService | None = None,
    ) -> None:
        self._upload_dir = Path(upload_dir)
        self._kb_service = kb_service or KnowledgeBaseService()

    def create_upload(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> Document:
        self._kb_service.get_for_user(session, user_id=user_id, kb_id=kb_id)
        stored_path = self._save_file(user_id=user_id, kb_id=kb_id, filename=filename, content=content)
        document = Document(
            kb_id=kb_id,
            user_id=user_id,
            filename=Path(filename).name,
            content_type=content_type,
            file_path=stored_path.as_posix(),
            status=DocumentStatus.PENDING,
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        return document

    def list_for_kb(self, session: Session, *, user_id: int, kb_id: int) -> list[Document]:
        self._kb_service.get_for_user(session, user_id=user_id, kb_id=kb_id)
        statement = (
            select(Document)
            .where(Document.user_id == user_id, Document.kb_id == kb_id)
            .order_by(Document.created_at.desc())
        )
        return list(session.scalars(statement))

    def get_for_user(self, session: Session, *, user_id: int, document_id: int) -> Document:
        statement = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        document = session.scalar(statement)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        return document

    def delete(self, session: Session, *, user_id: int, document_id: int) -> None:
        document = self.get_for_user(session, user_id=user_id, document_id=document_id)
        file_path = Path(document.file_path)
        session.delete(document)
        session.commit()
        if file_path.exists():
            file_path.unlink()

    def process_sync(self, session: Session, *, user_id: int, document_id: int) -> tuple[Document, int]:
        document = self.get_for_user(session, user_id=user_id, document_id=document_id)
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        session.commit()
        session.refresh(document)

        try:
            parsed_docs = parse_document_file(document.file_path)
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
            session.commit()
            session.refresh(document)
            raise

        document.status = DocumentStatus.COMPLETED
        document.error_message = None
        session.commit()
        session.refresh(document)
        return document, len(parsed_docs)

    def mark_failed(self, session: Session, *, user_id: int, document_id: int, error_message: str) -> Document:
        document = self.get_for_user(session, user_id=user_id, document_id=document_id)
        document.status = DocumentStatus.FAILED
        document.error_message = error_message
        session.commit()
        session.refresh(document)
        return document

    def _save_file(self, *, user_id: int, kb_id: int, filename: str, content: bytes) -> Path:
        safe_name = _safe_filename(filename)
        target_dir = self._upload_dir / str(user_id) / str(kb_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid4().hex}_{safe_name}"
        target_path.write_bytes(content)
        return target_path


def _safe_filename(filename: str) -> str:
    name = Path(filename or "upload.bin").name.strip() or "upload.bin"
    return re.sub(r"[^\w._-]+", "_", name, flags=re.UNICODE)


def get_document_service() -> DocumentService:
    return DocumentService()
