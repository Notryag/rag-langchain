from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.rate_limit import InMemoryRateLimiter


class RejectSecondRequestLimiter:
    def __init__(self) -> None:
        self.calls = 0

    def check(self, *, key: str, limit: int, window_seconds: int):
        from app.api.rate_limit import RateLimitResult

        self.calls += 1
        return RateLimitResult(allowed=self.calls == 1, remaining=0, retry_after_seconds=30)


class RateLimitTests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        if hasattr(app.state, "rate_limiter"):
            delattr(app.state, "rate_limiter")

    def test_in_memory_limiter_rejects_after_limit(self) -> None:
        limiter = InMemoryRateLimiter()

        first = limiter.check(key="k", limit=1, window_seconds=60)
        second = limiter.check(key="k", limit=1, window_seconds=60)

        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.remaining, 0)

    def test_api_returns_429_when_limited(self) -> None:
        app.state.rate_limiter = RejectSecondRequestLimiter()
        client = TestClient(app)

        first = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"})
        second = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"})

        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"]["code"], "rate_limit_exceeded")
        self.assertIn("retry-after", second.headers)


if __name__ == "__main__":
    unittest.main()
