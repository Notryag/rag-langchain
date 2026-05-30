from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

import app.api.routes as routes
from app.api.main import app
from app.services.rag_types import RagResponse, RagStreamEvent


class ApiSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_public_config(self) -> None:
        response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("chat_model", payload)
        self.assertIn("embedding_model", payload)
        self.assertIn("retrieval_search_type", payload)

    def test_create_thread(self) -> None:
        response = self.client.post("/api/threads")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["thread_id"].startswith("web_"))

    def test_react_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('<div id="root"></div>', response.text)

    def test_chat_stream_sse_contract(self) -> None:
        class FakeRagService:
            def stream(self, user_input: str, *, thread_id: str | None = None):
                self.last_user_input = user_input
                self.last_thread_id = thread_id
                yield RagStreamEvent(
                    type="tool_call",
                    tool_name="retrieve_context",
                    status_line="调用工具 retrieve_context",
                )
                yield RagStreamEvent(type="answer", content="答案", answer="答案")
                yield RagStreamEvent(
                    type="complete",
                    answer="答案",
                    result=RagResponse(thread_id=thread_id or "web_fake", answer="答案", elapsed_ms=12),
                )

        fake_service = FakeRagService()
        original_get_rag_service = routes.get_rag_service
        routes.get_rag_service = lambda: fake_service
        try:
            response = self.client.post(
                "/api/chat/stream",
                json={"message": "  测试问题  ", "thread_id": "web_test"},
            )
        finally:
            routes.get_rag_service = original_get_rag_service

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: tool_call", response.text)
        self.assertIn("event: answer", response.text)
        self.assertIn("event: complete", response.text)
        self.assertIn('"thread_id": "web_test"', response.text)
        self.assertEqual(fake_service.last_user_input, "测试问题")
        self.assertEqual(fake_service.last_thread_id, "web_test")


if __name__ == "__main__":
    unittest.main()
