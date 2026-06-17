from __future__ import annotations

import unittest
from types import SimpleNamespace

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

    def test_metrics(self) -> None:
        response = self.client.get("/api/metrics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("started_at", payload)
        self.assertIn("uptime_seconds", payload)
        self.assertIn("chat_requests_total", payload)
        self.assertIn("chat_stream_requests_total", payload)
        self.assertIn("chat_errors_total", payload)
        self.assertIn("feedback_total", payload)
        self.assertIn("average_chat_elapsed_ms", payload)

    def test_create_thread(self) -> None:
        response = self.client.post("/api/threads")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["thread_id"].startswith("web_"))

    def test_feedback_records_payload(self) -> None:
        class FakeFeedbackService:
            def record(self, **kwargs):
                self.last_kwargs = kwargs
                return SimpleNamespace(feedback_id="feedback_1")

        fake_service = FakeFeedbackService()
        original_get_feedback_service = routes.get_feedback_service
        routes.get_feedback_service = lambda: fake_service
        try:
            response = self.client.post(
                "/api/feedback",
                json={
                    "thread_id": "web_test",
                    "message_id": "message_1",
                    "rating": "down",
                    "question": " 测试问题 ",
                    "answer": " 测试回答 ",
                    "comment": " 引用不准确 ",
                    "citations": [{"source": "source.txt"}],
                    "metadata": {"search_type": "hybrid"},
                },
            )
        finally:
            routes.get_feedback_service = original_get_feedback_service

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"feedback_id": "feedback_1", "status": "recorded"})
        self.assertEqual(fake_service.last_kwargs["thread_id"], "web_test")
        self.assertEqual(fake_service.last_kwargs["message_id"], "message_1")
        self.assertEqual(fake_service.last_kwargs["rating"], "down")
        self.assertEqual(fake_service.last_kwargs["question"], "测试问题")
        self.assertEqual(fake_service.last_kwargs["answer"], "测试回答")
        self.assertEqual(fake_service.last_kwargs["comment"], "引用不准确")
        self.assertEqual(fake_service.last_kwargs["citations"], [{"source": "source.txt"}])
        self.assertEqual(fake_service.last_kwargs["metadata"], {"search_type": "hybrid"})

    def test_feedback_rejects_invalid_rating(self) -> None:
        response = self.client.post(
            "/api/feedback",
            json={
                "thread_id": "web_test",
                "message_id": "message_1",
                "rating": "maybe",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_react_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('<div id="root"></div>', response.text)

    def test_chat_stream_sse_contract(self) -> None:
        class FakeRagService:
            def stream(self, user_input: str, *, thread_id: str | None = None, retrieval_profile=None):
                self.last_user_input = user_input
                self.last_thread_id = thread_id
                self.last_retrieval_profile = retrieval_profile
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
                json={
                    "message": "  测试问题  ",
                    "thread_id": "web_test",
                    "retrieval_profile": {
                        "search_type": "mmr",
                        "top_k": 4,
                        "fetch_k": 10,
                        "reranker_enabled": True,
                        "max_context_chars": 1200,
                    },
                },
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
        self.assertEqual(fake_service.last_retrieval_profile.search_type, "mmr")
        self.assertEqual(fake_service.last_retrieval_profile.top_k, 4)

    def test_chat_rejects_invalid_retrieval_profile(self) -> None:
        response = self.client.post(
            "/api/chat/stream",
            json={
                "message": "测试问题",
                "retrieval_profile": {
                    "search_type": "unknown",
                    "top_k": 3,
                    "fetch_k": 8,
                },
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
