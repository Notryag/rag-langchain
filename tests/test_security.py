from __future__ import annotations

import unittest
from datetime import timedelta

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


class SecurityTests(unittest.TestCase):
    def test_hash_and_verify_password(self) -> None:
        password_hash = hash_password("password-123")

        self.assertNotEqual(password_hash, "password-123")
        self.assertTrue(verify_password("password-123", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token("42", expires_delta=timedelta(minutes=5))

        payload = decode_access_token(token)

        self.assertEqual(payload["sub"], "42")
        self.assertIn("exp", payload)

    def test_rejects_invalid_token(self) -> None:
        with self.assertRaises(ValueError):
            decode_access_token("not-a-token")


if __name__ == "__main__":
    unittest.main()
