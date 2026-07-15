from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.hot_question_cache import (
    CachedChatAnswer,
    InMemoryHotQuestionCache,
    build_hot_question_cache_key,
    build_hot_question_scope_key,
)


class HotQuestionCacheTests(unittest.TestCase):
    def test_cache_key_is_tenant_scoped(self) -> None:
        first = build_hot_question_cache_key(user_id=1, kb_id=1, question="怎么计费？", top_k=3)
        second = build_hot_question_cache_key(user_id=2, kb_id=1, question="怎么计费？", top_k=3)

        self.assertNotEqual(first, second)

    def test_in_memory_cache_invalidates_scope(self) -> None:
        cache = InMemoryHotQuestionCache()
        scope_key = build_hot_question_scope_key(user_id=1, kb_id=2)

        cache.set(
            key="answer-key",
            scope_key=scope_key,
            value=CachedChatAnswer(answer="answer", references=[]),
            ttl_seconds=60,
        )
        self.assertIsNotNone(cache.get(key="answer-key"))

        cache.invalidate_scope(scope_key=scope_key)

        self.assertIsNone(cache.get(key="answer-key"))

    def test_in_memory_cache_expires_items(self) -> None:
        cache = InMemoryHotQuestionCache()
        with patch("app.services.hot_question_cache.time.monotonic", return_value=10.0):
            cache.set(
                key="answer-key",
                scope_key="scope-key",
                value=CachedChatAnswer(answer="answer", references=[]),
                ttl_seconds=5,
            )

        with patch("app.services.hot_question_cache.time.monotonic", return_value=15.0):
            self.assertIsNone(cache.get(key="answer-key"))

    def test_cache_key_normalizes_question_whitespace_and_case(self) -> None:
        first = build_hot_question_cache_key(
            user_id=1,
            kb_id=2,
            question="  HOW   to reset? ",
            top_k=3,
        )
        second = build_hot_question_cache_key(
            user_id=1,
            kb_id=2,
            question="how to reset?",
            top_k=3,
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
