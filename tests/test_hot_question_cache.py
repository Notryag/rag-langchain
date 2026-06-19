from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.db.models.chat import ChatMessage
from app.services.chat_service import ChatService
from app.services.hot_question_cache import (
    CachedChatAnswer,
    InMemoryHotQuestionCache,
    build_hot_question_cache_key,
    build_hot_question_scope_key,
)


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = len(self.added) + 1
        self.added.append(item)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = len(self.added) + 1


class FakeKbService:
    def get_for_user(self, session, *, user_id, kb_id):
        return SimpleNamespace(id=kb_id, user_id=user_id)


class FakeChunk:
    def to_reference(self):
        return {"filename": "manual.txt", "chunk_index": 1, "content": "计费规则"}


class FakeModel:
    calls = 0

    def invoke(self, messages):
        self.calls += 1
        return SimpleNamespace(
            content="根据资料回答。",
            usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
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

    def test_chat_service_reuses_cached_answer_and_still_records_messages(self) -> None:
        cache = InMemoryHotQuestionCache()
        retriever_calls = []
        model = FakeModel()

        def retriever(session, *, user_id, kb_id, query, top_k):
            retriever_calls.append(query)
            return [FakeChunk()]

        service = ChatService(
            kb_service=FakeKbService(),
            retriever=retriever,
            chat_model=model,
            answer_cache=cache,
        )
        session = FakeSession()

        first = service.ask(session, user_id=1, kb_id=2, question="怎么计费？")
        second = service.ask(session, user_id=1, kb_id=2, question="怎么计费？")

        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.usage["total_tokens"], 10)
        self.assertTrue(second.usage["cached"])
        self.assertEqual(second.usage["total_tokens"], 10)
        self.assertEqual(retriever_calls, ["怎么计费？"])
        self.assertEqual(model.calls, 1)
        self.assertEqual(len([item for item in session.added if isinstance(item, ChatMessage)]), 4)


if __name__ == "__main__":
    unittest.main()
