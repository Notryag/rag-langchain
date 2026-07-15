from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models.document import Document, DocumentStatus
from app.retrieval.parser import parse_document_file
from app.retrieval.pgvector_store import ingest_document_chunks
from app.services.kb_service import KnowledgeBaseService


class DocumentNotFoundError(ValueError):
    pass


class DocumentUploadError(ValueError):
    pass


class DocumentTooLargeError(DocumentUploadError):
    pass


class DocumentAlreadyProcessingError(RuntimeError):
    pass


SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}
SUPPORTED_CONTENT_TYPES = {
    "application/octet-stream",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/html",
    "text/markdown",
    "text/plain",
}
UPLOAD_CHUNK_BYTES = 1024 * 1024


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
        return self.create_upload_file(
            session,
            user_id=user_id,
            kb_id=kb_id,
            filename=filename,
            content_type=content_type,
            source=BytesIO(content),
        )

    def create_upload_file(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        filename: str,
        content_type: str | None,
        source: BinaryIO,
    ) -> Document:
        self._kb_service.get_for_user(session, user_id=user_id, kb_id=kb_id)
        _validate_upload(filename=filename, content_type=content_type)
        stored_path = self._save_file_stream(
            user_id=user_id,
            kb_id=kb_id,
            filename=filename,
            source=source,
            max_bytes=settings.max_upload_bytes,
        )
        document = Document(
            kb_id=kb_id,
            user_id=user_id,
            filename=Path(filename).name,
            content_type=content_type,
            file_path=stored_path.as_posix(),
            status=DocumentStatus.PENDING,
        )
        try:
            session.add(document)
            session.commit()
            session.refresh(document)
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
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
        statement = (
            select(Document)
            .where(Document.id == document_id, Document.user_id == user_id)
            .with_for_update()
        )
        document = session.scalar(statement)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        if document.status == DocumentStatus.PROCESSING:
            raise DocumentAlreadyProcessingError("Document is already being processed")
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        session.commit()
        session.refresh(document)

        try:
            parsed_docs = parse_document_file(document.file_path)
            chunk_count = ingest_document_chunks(session, document=document, parsed_docs=parsed_docs)
        except Exception as exc:
            session.rollback()
            document = self.get_for_user(session, user_id=user_id, document_id=document_id)
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
            session.commit()
            session.refresh(document)
            raise

        document.status = DocumentStatus.COMPLETED
        document.error_message = None
        session.commit()
        session.refresh(document)
        return document, chunk_count

    def mark_failed(self, session: Session, *, user_id: int, document_id: int, error_message: str) -> Document:
        document = self.get_for_user(session, user_id=user_id, document_id=document_id)
        document.status = DocumentStatus.FAILED
        document.error_message = error_message
        session.commit()
        session.refresh(document)
        return document

    def _save_file(self, *, user_id: int, kb_id: int, filename: str, content: bytes) -> Path:
        return self._save_file_stream(
            user_id=user_id,
            kb_id=kb_id,
            filename=filename,
            source=BytesIO(content),
            max_bytes=settings.max_upload_bytes,
        )

    def _save_file_stream(
        self,
        *,
        user_id: int,
        kb_id: int,
        filename: str,
        source: BinaryIO,
        max_bytes: int,
    ) -> Path:
        safe_name = _safe_filename(filename)
        target_dir = self._upload_dir / str(user_id) / str(kb_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid4().hex}_{safe_name}"
        written = 0
        try:
            with target_path.open("xb") as target:
                while chunk := source.read(UPLOAD_CHUNK_BYTES):
                    written += len(chunk)
                    if written > max_bytes:
                        raise DocumentTooLargeError(f"Document exceeds the {max_bytes} byte upload limit")
                    target.write(chunk)
        except Exception:
            target_path.unlink(missing_ok=True)
            raise
        return target_path


def _safe_filename(filename: str) -> str:
    name = Path(filename or "upload.bin").name.strip() or "upload.bin"
    return re.sub(r"[^\w._-]+", "_", name, flags=re.UNICODE)


def _validate_upload(*, filename: str, content_type: str | None) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise DocumentUploadError(f"Unsupported document type: {suffix or '<none>'}")
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type and normalized_content_type not in SUPPORTED_CONTENT_TYPES:
        raise DocumentUploadError(f"Unsupported content type: {normalized_content_type}")


def get_document_service() -> DocumentService:
    return DocumentService()
