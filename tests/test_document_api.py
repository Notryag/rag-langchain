from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.v1 import auth as auth_routes
from app.api.v1 import documents as document_routes
from app.db.models.document import DocumentStatus
from app.services.document_service import DocumentNotFoundError
from app.services.kb_service import KnowledgeBaseNotFoundError


def _document(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": 3,
        "kb_id": 2,
        "user_id": 1,
        "filename": "manual.txt",
        "content_type": "text/plain",
        "file_path": "./storage/uploads/1/2/manual.txt",
        "status": DocumentStatus.PENDING,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class DocumentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        self.client = TestClient(app)
        self.current_user = SimpleNamespace(id=1, username="alice", email="alice@example.com")
        self.operation_logs: list[dict] = []
        app.dependency_overrides[auth_routes.get_current_user] = lambda: self.current_user
        app.dependency_overrides[document_routes.get_db_session] = lambda: object()
        self.dispatched_document_ids: list[int] = []
        app.dependency_overrides[document_routes.get_document_task_dispatcher] = (
            lambda: self.dispatched_document_ids.append
        )

        class FakeOperationLogService:
            def record(inner_self, session, **kwargs):
                self.operation_logs.append(kwargs)

        app.dependency_overrides[document_routes.get_operation_log_service] = lambda: FakeOperationLogService()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_upload_document(self) -> None:
        class FakeDocumentService:
            def create_upload(self, session, *, user_id, kb_id, filename, content_type, content):
                self.user_id = user_id
                self.kb_id = kb_id
                self.filename = filename
                self.content_type = content_type
                self.content = content
                return _document(kb_id=kb_id, filename=filename, content_type=content_type)

        fake_service = FakeDocumentService()
        app.dependency_overrides[document_routes.get_document_service] = lambda: fake_service

        response = self.client.post(
            "/api/v1/kbs/2/documents",
            files={"file": ("manual.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["filename"], "manual.txt")
        self.assertEqual(response.json()["status"], "pending")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.kb_id, 2)
        self.assertEqual(fake_service.content, b"hello")
        self.assertEqual(self.dispatched_document_ids, [3])
        self.assertEqual(self.operation_logs[0]["action"], "document.upload")
        self.assertEqual(self.operation_logs[0]["resource_id"], 3)

    def test_upload_document_rejects_missing_kb(self) -> None:
        class FakeDocumentService:
            def create_upload(self, session, *, user_id, kb_id, filename, content_type, content):
                raise KnowledgeBaseNotFoundError("Knowledge base not found")

        app.dependency_overrides[document_routes.get_document_service] = lambda: FakeDocumentService()

        response = self.client.post(
            "/api/v1/kbs/404/documents",
            files={"file": ("manual.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "knowledge_base_not_found")
        self.assertEqual(self.dispatched_document_ids, [])

    def test_list_documents(self) -> None:
        class FakeDocumentService:
            def list_for_kb(self, session, *, user_id, kb_id):
                self.user_id = user_id
                self.kb_id = kb_id
                return [_document(id=1), _document(id=2, status=DocumentStatus.COMPLETED)]

        fake_service = FakeDocumentService()
        app.dependency_overrides[document_routes.get_document_service] = lambda: fake_service

        response = self.client.get("/api/v1/kbs/2/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [1, 2])
        self.assertEqual(response.json()[1]["status"], "completed")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.kb_id, 2)

    def test_get_document(self) -> None:
        class FakeDocumentService:
            def get_for_user(self, session, *, user_id, document_id):
                self.user_id = user_id
                self.document_id = document_id
                return _document(id=document_id)

        fake_service = FakeDocumentService()
        app.dependency_overrides[document_routes.get_document_service] = lambda: fake_service

        response = self.client.get("/api/v1/documents/3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 3)
        self.assertEqual(fake_service.user_id, 1)

    def test_delete_document(self) -> None:
        class FakeDocumentService:
            def delete(self, session, *, user_id, document_id):
                self.user_id = user_id
                self.document_id = document_id

        fake_service = FakeDocumentService()
        app.dependency_overrides[document_routes.get_document_service] = lambda: fake_service

        response = self.client.delete("/api/v1/documents/3")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.document_id, 3)
        self.assertEqual(self.operation_logs[0]["action"], "document.delete")

    def test_process_document(self) -> None:
        class FakeDocumentService:
            def process_sync(self, session, *, user_id, document_id):
                self.user_id = user_id
                self.document_id = document_id
                return _document(id=document_id, status=DocumentStatus.COMPLETED), 1

        fake_service = FakeDocumentService()
        app.dependency_overrides[document_routes.get_document_service] = lambda: fake_service

        response = self.client.post("/api/v1/documents/3/process")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["parsed_units"], 1)
        self.assertEqual(response.json()["chunk_count"], 1)
        self.assertEqual(response.json()["document"]["status"], "completed")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(self.operation_logs[0]["action"], "document.process")
        self.assertEqual(self.operation_logs[0]["details"]["chunk_count"], 1)

    def test_missing_document_returns_404(self) -> None:
        class FakeDocumentService:
            def get_for_user(self, session, *, user_id, document_id):
                raise DocumentNotFoundError("Document not found")

        app.dependency_overrides[document_routes.get_document_service] = lambda: FakeDocumentService()

        response = self.client.get("/api/v1/documents/404")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "document_not_found")

    def test_process_document_failure_returns_structured_error(self) -> None:
        class FakeDocumentService:
            def process_sync(self, session, *, user_id, document_id):
                raise RuntimeError("unsupported file")

        app.dependency_overrides[document_routes.get_document_service] = lambda: FakeDocumentService()

        response = self.client.post("/api/v1/documents/3/process")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "document_processing_failed")


if __name__ == "__main__":
    unittest.main()
