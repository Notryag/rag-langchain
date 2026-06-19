from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api.main import app


class ApiSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_public_config(self) -> None:
        response = self.client.get("/api/v1/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("chat_model", payload)
        self.assertIn("embedding_model", payload)
        self.assertIn("embedding_dimension", payload)
        self.assertIn("retrieval_search_type", payload)
        self.assertNotIn("collection_name", payload)

    def test_metrics(self) -> None:
        response = self.client.get("/api/v1/metrics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("started_at", payload)
        self.assertIn("uptime_seconds", payload)
        self.assertIn("chat_requests_total", payload)
        self.assertIn("chat_stream_requests_total", payload)
        self.assertIn("chat_errors_total", payload)
        self.assertIn("feedback_total", payload)
        self.assertIn("average_chat_elapsed_ms", payload)

    def test_react_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('<div id="root"></div>', response.text)


if __name__ == "__main__":
    unittest.main()
