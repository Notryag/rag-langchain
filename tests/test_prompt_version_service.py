from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.prompt_version_service import (
    DEFAULT_PROMPT_NAME,
    DEFAULT_PROMPT_VERSION,
    PromptVersionService,
)


class FakeSession:
    def __init__(self, scalar_result=None):
        self.scalar_result = scalar_result
        self.added = []
        self.commits = 0
        self.refreshed = []

    def scalar(self, statement):
        self.statement = statement
        return self.scalar_result

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        value.id = getattr(value, "id", None) or 1
        self.refreshed.append(value)


class PromptVersionServiceTests(unittest.TestCase):
    def test_ensure_default_reuses_active_version(self) -> None:
        existing = SimpleNamespace(id=3, is_active=True)
        session = FakeSession(existing)

        prompt = PromptVersionService().ensure_default(session)

        self.assertIs(prompt, existing)
        self.assertEqual(session.commits, 0)

    def test_ensure_default_creates_default_version(self) -> None:
        session = FakeSession(None)

        prompt = PromptVersionService().ensure_default(session)

        self.assertEqual(prompt.name, DEFAULT_PROMPT_NAME)
        self.assertEqual(prompt.version, DEFAULT_PROMPT_VERSION)
        self.assertTrue(prompt.is_active)
        self.assertEqual(session.commits, 1)
        self.assertEqual(len(session.added), 1)


if __name__ == "__main__":
    unittest.main()
