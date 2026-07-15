from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.v1 import auth as auth_routes
from app.api.v1 import prompts as prompt_routes
from app.db.models.user import UserRole
from app.services.prompt_version_service import PromptVersionConflictError, PromptVersionNotFoundError


def _prompt(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": 1,
        "name": "default_rag_assistant",
        "version": "v1",
        "description": "default",
        "system_prompt": "You are helpful.",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class PromptApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        self.client = TestClient(app)
        self.current_user = SimpleNamespace(
            id=1,
            username="alice",
            email="alice@example.com",
            role=UserRole.ADMIN,
        )
        self.operation_logs: list[dict] = []
        app.dependency_overrides[auth_routes.get_current_user] = lambda: self.current_user
        app.dependency_overrides[prompt_routes.get_db_session] = lambda: object()

        class FakeOperationLogService:
            def record(inner_self, session, **kwargs):
                self.operation_logs.append(kwargs)

        app.dependency_overrides[prompt_routes.get_operation_log_service] = lambda: FakeOperationLogService()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_list_prompt_versions(self) -> None:
        class FakePromptService:
            def list_versions(self, session):
                return [_prompt(id=2, version="v2"), _prompt(id=1, version="v1", is_active=False)]

        app.dependency_overrides[prompt_routes.get_prompt_version_service] = lambda: FakePromptService()

        response = self.client.get("/api/v1/prompts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["version"] for item in response.json()], ["v2", "v1"])

    def test_regular_user_cannot_manage_prompts(self) -> None:
        self.current_user.role = UserRole.USER

        response = self.client.get("/api/v1/prompts")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "admin_required")

    def test_create_prompt_version(self) -> None:
        class FakePromptService:
            def create(self, session, payload):
                self.payload = payload
                return _prompt(id=3, name=payload.name, version=payload.version, system_prompt=payload.system_prompt)

        fake_service = FakePromptService()
        app.dependency_overrides[prompt_routes.get_prompt_version_service] = lambda: fake_service

        response = self.client.post(
            "/api/v1/prompts",
            json={"name": "rag", "version": "v2", "system_prompt": "answer with citations"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], 3)
        self.assertEqual(fake_service.payload.system_prompt, "answer with citations")
        self.assertEqual(self.operation_logs[0]["action"], "prompt.create")
        self.assertEqual(self.operation_logs[0]["resource_id"], 3)

    def test_create_prompt_version_conflict(self) -> None:
        class FakePromptService:
            def create(self, session, payload):
                raise PromptVersionConflictError("Prompt version already exists")

        app.dependency_overrides[prompt_routes.get_prompt_version_service] = lambda: FakePromptService()

        response = self.client.post(
            "/api/v1/prompts",
            json={"name": "rag", "version": "v1", "system_prompt": "prompt"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "prompt_version_conflict")

    def test_activate_prompt_version(self) -> None:
        class FakePromptService:
            def activate(self, session, prompt_version_id):
                self.prompt_version_id = prompt_version_id
                return _prompt(id=prompt_version_id, version="v2")

        fake_service = FakePromptService()
        app.dependency_overrides[prompt_routes.get_prompt_version_service] = lambda: fake_service

        response = self.client.post("/api/v1/prompts/2/activate")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 2)
        self.assertEqual(fake_service.prompt_version_id, 2)
        self.assertEqual(self.operation_logs[0]["action"], "prompt.activate")

    def test_rollback_prompt_version(self) -> None:
        class FakePromptService:
            def activate(self, session, prompt_version_id):
                return _prompt(id=prompt_version_id, version="v1")

        app.dependency_overrides[prompt_routes.get_prompt_version_service] = lambda: FakePromptService()

        response = self.client.post("/api/v1/prompts/1/rollback")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.operation_logs[0]["action"], "prompt.rollback")

    def test_activate_prompt_version_missing(self) -> None:
        class FakePromptService:
            def activate(self, session, prompt_version_id):
                raise PromptVersionNotFoundError("Prompt version not found")

        app.dependency_overrides[prompt_routes.get_prompt_version_service] = lambda: FakePromptService()

        response = self.client.post("/api/v1/prompts/404/activate")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "prompt_version_not_found")


if __name__ == "__main__":
    unittest.main()
