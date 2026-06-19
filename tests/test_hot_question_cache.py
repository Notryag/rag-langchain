from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.db.models.chat import ChatMessage, ChatRun, ChatRunStatus
from app.services.chat_service import ChatService, _build_reference_context
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

    def __init__(self) -> None:
        self.last_messages = None

    def invoke(self, messages):
        self.calls += 1
        self.last_messages = messages
        return SimpleNamespace(
            content="根据资料回答。",
            usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        )


class FakeStreamingModel:
    def __init__(self) -> None:
        self.stream_calls = 0

    def stream(self, messages):
        self.stream_calls += 1
        yield SimpleNamespace(content="根据", usage_metadata={"input_tokens": 7, "output_tokens": 1, "total_tokens": 8})
        yield SimpleNamespace(content="资料回答。", usage_metadata={"input_tokens": 0, "output_tokens": 2, "total_tokens": 2})


class HotQuestionCacheTests(unittest.TestCase):
    def test_build_reference_context_respects_char_budget(self) -> None:
        references = [
            {
                "filename": "manual.txt",
                "chunk_index": 1,
                "content": "计费规则包括调用次数和存储容量。" * 20,
            }
        ]

        context = _build_reference_context(references, max_context_chars=80)

        self.assertLessEqual(len(context), 80)
        self.assertIn("filename=manual.txt", context)
        self.assertTrue(context.endswith("..."))

    def test_build_reference_context_skips_when_budget_cannot_fit_header(self) -> None:
        context = _build_reference_context(
            [{"filename": "manual.txt", "chunk_index": 1, "content": "计费规则"}],
            max_context_chars=5,
        )

        self.assertEqual(context, "")

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
        runs = [item for item in session.added if isinstance(item, ChatRun)]
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run.status == ChatRunStatus.COMPLETED for run in runs))
        self.assertFalse(runs[0].cache_hit)
        self.assertTrue(runs[1].cache_hit)

    def test_chat_service_compresses_prompt_context_without_truncating_references(self) -> None:
        long_content = "计费规则包括调用次数和存储容量。" * 400

        class LongChunk:
            def to_reference(self):
                return {"filename": "manual.txt", "chunk_index": 1, "content": long_content}

        def retriever(session, *, user_id, kb_id, query, top_k):
            return [LongChunk()]

        model = FakeModel()
        service = ChatService(
            kb_service=FakeKbService(),
            retriever=retriever,
            chat_model=model,
            answer_cache=InMemoryHotQuestionCache(),
        )
        session = FakeSession()

        answer = service.ask(session, user_id=1, kb_id=2, question="怎么计费？")

        prompt = model.last_messages[-1].content
        self.assertLess(len(prompt), len(long_content))
        self.assertEqual(answer.references[0]["content"], long_content)

    def test_chat_service_marks_run_failed_when_retriever_fails(self) -> None:
        def failing_retriever(session, *, user_id, kb_id, query, top_k):
            raise RuntimeError("retriever failed")

        service = ChatService(
            kb_service=FakeKbService(),
            retriever=failing_retriever,
            chat_model=FakeModel(),
            answer_cache=InMemoryHotQuestionCache(),
        )
        session = FakeSession()

        with self.assertRaises(RuntimeError):
            service.ask(session, user_id=1, kb_id=2, question="怎么计费？")

        runs = [item for item in session.added if isinstance(item, ChatRun)]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, ChatRunStatus.FAILED)
        self.assertEqual(runs[0].error_message, "retriever failed")

    def test_chat_service_streams_model_deltas_and_completes_run(self) -> None:
        cache = InMemoryHotQuestionCache()
        model = FakeStreamingModel()

        def retriever(session, *, user_id, kb_id, query, top_k):
            return [FakeChunk()]

        service = ChatService(
            kb_service=FakeKbService(),
            retriever=retriever,
            chat_model=model,
            answer_cache=cache,
        )
        session = FakeSession()

        events = list(service.stream(session, user_id=1, kb_id=2, question="怎么计费？"))

        self.assertEqual([event.type for event in events], ["answer_delta", "answer_delta", "complete"])
        self.assertEqual(events[0].content, "根据")
        self.assertEqual(events[1].answer, "根据资料回答。")
        self.assertEqual(events[-1].result.answer, "根据资料回答。")
        self.assertEqual(events[-1].result.usage["total_tokens"], 10)
        self.assertEqual(model.stream_calls, 1)
        runs = [item for item in session.added if isinstance(item, ChatRun)]
        self.assertEqual(runs[0].status, ChatRunStatus.COMPLETED)

    def test_chat_service_streams_cached_answer_without_model_call(self) -> None:
        cache = InMemoryHotQuestionCache()
        model = FakeStreamingModel()

        def retriever(session, *, user_id, kb_id, query, top_k):
            return [FakeChunk()]

        service = ChatService(
            kb_service=FakeKbService(),
            retriever=retriever,
            chat_model=model,
            answer_cache=cache,
        )
        session = FakeSession()

        list(service.stream(session, user_id=1, kb_id=2, question="怎么计费？"))
        second_events = list(service.stream(session, user_id=1, kb_id=2, question="怎么计费？"))

        self.assertEqual(model.stream_calls, 1)
        self.assertEqual(second_events[-1].type, "complete")
        self.assertTrue(second_events[-1].result.cache_hit)
        self.assertTrue(second_events[-1].result.usage["cached"])


if __name__ == "__main__":
    unittest.main()
