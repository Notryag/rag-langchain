from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.v1 import auth as auth_routes
from app.api.v1 import chat as chat_routes
from app.db.models.chat import ChatRole
from app.runtime.schemas import RuntimeRun, StreamEvent
from app.services.chat_service import ChatAnswer, ChatSessionNotFoundError


def _chat_session(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": 8,
        "user_id": 1,
        "kb_id": 2,
        "title": "怎么计费",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _chat_message(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": 9,
        "session_id": 8,
        "role": ChatRole.ASSISTANT,
        "content": "根据资料回答",
        "references": [{"filename": "产品说明.pdf"}],
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _chat_run_event(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": 10,
        "run_id": 34,
        "user_id": 1,
        "kb_id": 2,
        "event_type": "tool_result",
        "sequence": 1,
        "payload": {"tool_name": "retrieve_context", "citations": [{"filename": "产品说明.pdf"}]},
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        self.client = TestClient(app)
        self.current_user = SimpleNamespace(id=1, username="alice", email="alice@example.com")
        self.operation_logs: list[dict] = []
        app.dependency_overrides[auth_routes.get_current_user] = lambda: self.current_user
        app.dependency_overrides[chat_routes.get_db_session] = lambda: object()

        class FakeOperationLogService:
            def record(inner_self, session, **kwargs):
                self.operation_logs.append(kwargs)

        app.dependency_overrides[chat_routes.get_operation_log_service] = lambda: FakeOperationLogService()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_chat(self) -> None:
        class FakeChatService:
            def ask(self, session, *, user_id, kb_id, question, session_id=None):
                self.user_id = user_id
                self.kb_id = kb_id
                self.question = question
                self.session_id = session_id
                return ChatAnswer(
                    answer="系统根据调用次数计费。",
                    references=[{"filename": "产品说明.pdf", "chunk_index": 3}],
                    session_id=12,
                    run_id=34,
                    usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cached": False},
                    token_cost={"total_cost": 0.0, "currency": "USD"},
                )

        fake_service = FakeChatService()
        app.dependency_overrides[chat_routes.get_chat_service] = lambda: fake_service

        response = self.client.post(
            "/api/v1/kbs/2/chat",
            json={"question": "  怎么计费？ ", "session_id": 12},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], 12)
        self.assertEqual(response.json()["run_id"], 34)
        self.assertEqual(response.json()["references"][0]["filename"], "产品说明.pdf")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.kb_id, 2)
        self.assertEqual(fake_service.question, "怎么计费？")
        self.assertEqual(fake_service.session_id, 12)
        self.assertEqual(self.operation_logs[0]["action"], "chat.ask")
        self.assertEqual(self.operation_logs[0]["resource_type"], "chat_run")
        self.assertEqual(self.operation_logs[0]["resource_id"], 34)
        self.assertEqual(self.operation_logs[0]["details"]["session_id"], 12)
        self.assertEqual(self.operation_logs[0]["details"]["reference_count"], 1)
        self.assertFalse(self.operation_logs[0]["details"]["cache_hit"])
        self.assertEqual(response.json()["usage"]["total_tokens"], 15)
        self.assertEqual(response.json()["token_cost"]["total_cost"], 0.0)
        self.assertEqual(self.operation_logs[0]["details"]["usage"]["total_tokens"], 15)
        self.assertEqual(self.operation_logs[0]["details"]["token_cost"]["total_cost"], 0.0)

    def test_chat_returns_404_for_missing_session(self) -> None:
        class FakeChatService:
            def ask(self, session, *, user_id, kb_id, question, session_id=None):
                raise ChatSessionNotFoundError("Chat session not found")

        app.dependency_overrides[chat_routes.get_chat_service] = lambda: FakeChatService()

        response = self.client.post("/api/v1/kbs/2/chat", json={"question": "问题", "session_id": 404})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "chat_session_not_found")

    def test_chat_stream(self) -> None:
        class FakeRuntimeService:
            async def start_chat_run(self, session, *, user_id, kb_id, question, session_id=None):
                self.user_id = user_id
                self.kb_id = kb_id
                self.question = question
                self.session_id = session_id
                return RuntimeRun(run_id=34, session_id=12, user_id=user_id, kb_id=kb_id)

            async def stream_run(self, run_id, *, disconnect_mode):
                yield StreamEvent(id=1, event="answer_delta", data={"content": "系统", "answer": "系统"})
                yield StreamEvent(
                    id=2,
                    event="complete",
                    data={
                        "answer": "系统根据调用次数计费。",
                        "references": [{"filename": "产品说明.pdf", "chunk_index": 3}],
                        "session_id": 12,
                        "run_id": 34,
                        "cache_hit": False,
                        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cached": False},
                        "token_cost": {"total_cost": 0.0, "currency": "USD"},
                    },
                )
                yield StreamEvent(id=0, event="end", data={})

        fake_service = FakeRuntimeService()
        app.dependency_overrides[chat_routes.get_runtime_service] = lambda: fake_service

        with self.client.stream("POST", "/api/v1/kbs/2/chat/stream", json={"question": "怎么计费？"}) as response:
            body = response.read().decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: answer_delta", body)
        self.assertIn("event: complete", body)
        self.assertIn('"session_id": 12', body)
        self.assertIn('"run_id": 34', body)
        self.assertIn('"total_tokens": 15', body)
        self.assertIn('"total_cost": 0.0', body)
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.kb_id, 2)
        self.assertEqual(self.operation_logs[0]["action"], "chat.run.start")
        self.assertEqual(self.operation_logs[1]["action"], "chat.stream")
        self.assertEqual(self.operation_logs[1]["resource_type"], "chat_run")
        self.assertEqual(self.operation_logs[1]["resource_id"], 34)
        self.assertEqual(self.operation_logs[1]["details"]["session_id"], 12)
        self.assertEqual(self.operation_logs[1]["details"]["token_cost"]["total_cost"], 0.0)

    def test_list_chat_sessions(self) -> None:
        class FakeChatService:
            def list_sessions(self, session, *, user_id):
                self.user_id = user_id
                return [_chat_session(id=1), _chat_session(id=2)]

        fake_service = FakeChatService()
        app.dependency_overrides[chat_routes.get_chat_service] = lambda: fake_service

        response = self.client.get("/api/v1/chat-sessions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [1, 2])
        self.assertEqual(fake_service.user_id, 1)

    def test_list_chat_messages(self) -> None:
        class FakeChatService:
            def list_messages(self, session, *, user_id, session_id):
                self.user_id = user_id
                self.session_id = session_id
                return [_chat_message(id=1, role=ChatRole.USER, references=[]), _chat_message(id=2)]

        fake_service = FakeChatService()
        app.dependency_overrides[chat_routes.get_chat_service] = lambda: fake_service

        response = self.client.get("/api/v1/chat-sessions/8/messages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [1, 2])
        self.assertEqual(response.json()[0]["role"], "user")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.session_id, 8)

    def test_list_chat_run_events(self) -> None:
        class FakeChatService:
            def list_run_events(self, session, *, user_id, run_id):
                self.user_id = user_id
                self.run_id = run_id
                return [_chat_run_event(sequence=1), _chat_run_event(id=11, event_type="complete", sequence=2)]

        fake_service = FakeChatService()
        app.dependency_overrides[chat_routes.get_chat_service] = lambda: fake_service

        response = self.client.get("/api/v1/chat-runs/34/events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["event_type"] for item in response.json()], ["tool_result", "complete"])
        self.assertEqual(response.json()[0]["payload"]["tool_name"], "retrieve_context")
        self.assertEqual(fake_service.user_id, 1)
        self.assertEqual(fake_service.run_id, 34)


if __name__ == "__main__":
    unittest.main()
