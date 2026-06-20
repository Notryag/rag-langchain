from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.db.models.prompt import PromptVersion
from app.schemas.prompt import PromptVersionCreate
from app.services.prompt_version_service import (
    DEFAULT_PROMPT_NAME,
    DEFAULT_PROMPT_VERSION,
    PromptVersionConflictError,
    PromptVersionNotFoundError,
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

    def scalars(self, statement):
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

    def test_create_rejects_duplicate_name_and_version(self) -> None:
        session = FakeSession(SimpleNamespace(id=1))

        with self.assertRaises(PromptVersionConflictError):
            PromptVersionService().create(
                session,
                PromptVersionCreate(name="default", version="v1", system_prompt="prompt"),
            )

    def test_create_adds_inactive_prompt_version(self) -> None:
        session = FakeSession(None)

        prompt = PromptVersionService().create(
            session,
            PromptVersionCreate(
                name=" assistant ",
                version=" v2 ",
                description="test",
                system_prompt="new prompt",
            ),
        )

        self.assertEqual(prompt.name, "assistant")
        self.assertEqual(prompt.version, "v2")
        self.assertEqual(prompt.system_prompt, "new prompt")
        self.assertFalse(prompt.is_active)
        self.assertEqual(session.commits, 1)
        self.assertEqual(len(session.added), 1)

    def test_activate_marks_selected_version_active(self) -> None:
        prompt = PromptVersion(name="default", version="v2", system_prompt="prompt", is_active=False)
        prompt.id = 2
        session = Mock()
        session.get.return_value = prompt

        activated = PromptVersionService().activate(session, 2)

        self.assertIs(activated, prompt)
        self.assertTrue(prompt.is_active)
        session.execute.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(prompt)

    def test_activate_raises_when_missing(self) -> None:
        session = Mock()
        session.get.return_value = None

        with self.assertRaises(PromptVersionNotFoundError):
            PromptVersionService().activate(session, 404)


if __name__ == "__main__":
    unittest.main()
