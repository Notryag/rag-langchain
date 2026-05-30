from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api.main import app


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


if __name__ == "__main__":
    unittest.main()
