from __future__ import annotations

import unittest
from dataclasses import replace

from tests.test_checkpointer import _settings_for_checkpointer


class SettingsTests(unittest.TestCase):
    def test_langsmith_tracing_requires_api_key(self) -> None:
        with self.assertRaises(ValueError):
            replace(_settings_for_checkpointer("memory"), langsmith_tracing=True, langsmith_api_key=None)


if __name__ == "__main__":
    unittest.main()
