from __future__ import annotations

import logging

from app.db.models.document import Document
from app.db.session import get_session_factory
from app.services.document_service import DocumentAlreadyProcessingError, DocumentService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="documents.process",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=330,
)
def process_document_task(self, document_id: int) -> dict[str, int | str]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        document = session.get(Document, document_id)
        if document is None:
            logger.warning("异步文档处理跳过，文档不存在。document_id=%s", document_id)
            return {"document_id": document_id, "status": "missing", "chunk_count": 0}

        try:
            processed_document, chunk_count = DocumentService().process_sync(
                session,
                user_id=document.user_id,
                document_id=document.id,
            )
        except DocumentAlreadyProcessingError:
            logger.info("异步文档处理跳过，已有任务正在执行。document_id=%s", document_id)
            return {"document_id": document_id, "status": "already_processing", "chunk_count": 0}
        except Exception as exc:
            countdown = min(60, 2 ** (self.request.retries + 1))
            logger.exception(
                "异步文档处理失败，准备重试。document_id=%s retries=%s countdown=%s",
                document_id,
                self.request.retries,
                countdown,
            )
            raise self.retry(exc=exc, countdown=countdown)
        return {
            "document_id": processed_document.id,
            "status": processed_document.status.value,
            "chunk_count": chunk_count,
        }
    finally:
        session.close()


def enqueue_document_processing(document_id: int) -> str:
    result = process_document_task.delay(document_id)
    return str(result.id)


def get_document_task_dispatcher():
    return enqueue_document_processing
