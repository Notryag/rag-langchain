from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.v1 import auth as auth_routes
from app.api.v1 import knowledge_bases as kb_routes
from app.services.kb_service import KnowledgeBaseNotFoundError


def _kb(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": 10,
        "user_id": 1,
        "name": "默认知识库",
        "description": "说明",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class KnowledgeBaseApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        self.client = TestClient(app)
        self.current_user = SimpleNamespace(id=1, username="alice", email="alice@example.com")
        self.operation_logs: list[dict] = []
        app.dependency_overrides[auth_routes.get_current_user] = lambda: self.current_user
        app.dependency_overrides[kb_routes.get_db_session] = lambda: object()

        class FakeOperationLogService:
            def record(inner_self, session, **kwargs):
                self.operation_logs.append(kwargs)

        app.dependency_overrides[kb_routes.get_operation_log_service] = lambda: FakeOperationLogService()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_create_knowledge_base(self) -> None:
        class FakeKbService:
            def create(self, session, *, user_id, payload):
                self.user_id = user_id
                self.payload = payload
                return _kb(name=payload.name.strip(), description=payload.description)

        fake_service = FakeKbService()
        app.dependency_overrides[kb_routes.get_kb_service] = lambda: fake_service

        response = self.client.post("/api/v1/kbs", json={"name": " 产品知识库 ", "description": "公开资料"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "产品知识库")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(self.operation_logs[0]["action"], "kb.create")
        self.assertEqual(self.operation_logs[0]["resource_id"], 10)

    def test_list_knowledge_bases(self) -> None:
        class FakeKbService:
            def list_for_user(self, session, *, user_id):
                self.user_id = user_id
                return [_kb(id=1, name="A"), _kb(id=2, name="B")]

        fake_service = FakeKbService()
        app.dependency_overrides[kb_routes.get_kb_service] = lambda: fake_service

        response = self.client.get("/api/v1/kbs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json()], ["A", "B"])
        self.assertEqual(fake_service.user_id, 1)

    def test_get_knowledge_base(self) -> None:
        class FakeKbService:
            def get_for_user(self, session, *, user_id, kb_id):
                self.user_id = user_id
                self.kb_id = kb_id
                return _kb(id=kb_id)

        fake_service = FakeKbService()
        app.dependency_overrides[kb_routes.get_kb_service] = lambda: fake_service

        response = self.client.get("/api/v1/kbs/12")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 12)
        self.assertEqual(fake_service.user_id, 1)

    def test_update_knowledge_base(self) -> None:
        class FakeKbService:
            def update(self, session, *, user_id, kb_id, payload):
                self.user_id = user_id
                self.kb_id = kb_id
                self.payload = payload
                return _kb(id=kb_id, name=payload.name, description=payload.description)

        fake_service = FakeKbService()
        app.dependency_overrides[kb_routes.get_kb_service] = lambda: fake_service

        response = self.client.put("/api/v1/kbs/12", json={"name": "售后知识库", "description": "FAQ"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "售后知识库")
        self.assertEqual(fake_service.kb_id, 12)
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(self.operation_logs[0]["action"], "kb.update")

    def test_delete_knowledge_base(self) -> None:
        class FakeKbService:
            def delete(self, session, *, user_id, kb_id):
                self.user_id = user_id
                self.kb_id = kb_id

        fake_service = FakeKbService()
        app.dependency_overrides[kb_routes.get_kb_service] = lambda: fake_service

        response = self.client.delete("/api/v1/kbs/12")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(fake_service.kb_id, 12)
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(self.operation_logs[0]["action"], "kb.delete")
        self.assertEqual(self.operation_logs[0]["resource_id"], 12)

    def test_returns_404_when_knowledge_base_is_missing(self) -> None:
        class FakeKbService:
            def get_for_user(self, session, *, user_id, kb_id):
                raise KnowledgeBaseNotFoundError("Knowledge base not found")

        app.dependency_overrides[kb_routes.get_kb_service] = lambda: FakeKbService()

        response = self.client.get("/api/v1/kbs/404")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "knowledge_base_not_found")


if __name__ == "__main__":
    unittest.main()
