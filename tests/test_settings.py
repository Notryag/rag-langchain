from __future__ import annotations

import unittest
from dataclasses import replace

from tests.test_checkpointer import _settings_for_checkpointer


class SettingsTests(unittest.TestCase):
    def test_langsmith_tracing_requires_api_key(self) -> None:
        with self.assertRaises(ValueError):
            replace(_settings_for_checkpointer("memory"), langsmith_tracing=True, langsmith_api_key=None)

    def test_http_reranker_requires_url_when_enabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "RERANKER_API_URL"):
            replace(
                _settings_for_checkpointer("memory"),
                reranker_enabled=True,
                reranker_strategy="http",
                reranker_api_url=None,
            )

    def test_reranker_timeout_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "RERANKER_TIMEOUT_SECONDS"):
            replace(_settings_for_checkpointer("memory"), reranker_timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
