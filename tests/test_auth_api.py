from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.v1 import auth as auth_routes
from app.schemas.auth import TokenResponse, UserRead
from app.services.auth_service import AuthError


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_register(self) -> None:
        class FakeAuthService:
            def register(self, session, payload):
                self.payload = payload
                return SimpleNamespace(id=1, username=payload.username.strip().lower(), email=payload.email.strip().lower())

        fake_service = FakeAuthService()
        app.dependency_overrides[auth_routes.get_db_session] = lambda: object()
        app.dependency_overrides[auth_routes.get_auth_service] = lambda: fake_service

        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": " Alice ",
                "email": " Alice@Example.com ",
                "password": "password-123",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": 1, "username": "alice", "email": "alice@example.com"})

    def test_register_conflict(self) -> None:
        class FakeAuthService:
            def register(self, session, payload):
                raise AuthError("Username or email already exists")

        app.dependency_overrides[auth_routes.get_db_session] = lambda: object()
        app.dependency_overrides[auth_routes.get_auth_service] = lambda: FakeAuthService()

        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "password-123",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "auth_conflict")

    def test_login(self) -> None:
        class FakeAuthService:
            def login(self, session, *, username_or_email, password):
                self.username_or_email = username_or_email
                self.password = password
                return TokenResponse(
                    access_token="token",
                    user=UserRead(id=1, username="alice", email="alice@example.com"),
                )

        fake_service = FakeAuthService()
        app.dependency_overrides[auth_routes.get_db_session] = lambda: object()
        app.dependency_overrides[auth_routes.get_auth_service] = lambda: fake_service

        response = self.client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "alice", "password": "password-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "token")
        self.assertEqual(response.json()["token_type"], "bearer")
        self.assertEqual(response.json()["user"]["username"], "alice")
        self.assertEqual(fake_service.username_or_email, "alice")

    def test_login_rejects_invalid_credentials(self) -> None:
        class FakeAuthService:
            def login(self, session, *, username_or_email, password):
                raise AuthError("Invalid username/email or password")

        app.dependency_overrides[auth_routes.get_db_session] = lambda: object()
        app.dependency_overrides[auth_routes.get_auth_service] = lambda: FakeAuthService()

        response = self.client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "alice", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

    def test_me(self) -> None:
        app.dependency_overrides[auth_routes.get_current_user] = lambda: SimpleNamespace(
            id=1,
            username="alice",
            email="alice@example.com",
        )

        response = self.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1, "username": "alice", "email": "alice@example.com"})


if __name__ == "__main__":
    unittest.main()
