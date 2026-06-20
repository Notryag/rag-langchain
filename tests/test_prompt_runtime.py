from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.db.models.chat import ChatRun
from app.services.chat_service import ChatService
from app.services.rag_types import RagResponse, RagStreamEvent


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


class FakePromptVersionService:
    prompt = SimpleNamespace(id=42, system_prompt="Use strict citations.")

    def get_active(self, session):
        return self.prompt


class FakeRagService:
    def __init__(self) -> None:
        self.system_prompt = None

    def stream(self, question, **kwargs):
        self.system_prompt = kwargs.get("system_prompt")
        yield RagStreamEvent(type="answer", content="回答", answer="回答")
        yield RagStreamEvent(
            type="complete",
            result=RagResponse(
                thread_id=kwargs["thread_id"],
                answer="回答",
                citations=[{"filename": "manual.txt", "chunk_index": 1, "content": "source"}],
                usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cached": False},
            ),
        )


class PromptRuntimeTests(unittest.TestCase):
    def test_chat_uses_active_prompt_version_system_prompt(self) -> None:
        rag_service = FakeRagService()
        service = ChatService(
            kb_service=FakeKbService(),
            rag_service=rag_service,
            prompt_version_service=FakePromptVersionService(),
        )
        session = FakeSession()

        answer = service.ask(session, user_id=1, kb_id=2, question="怎么计费？")

        self.assertEqual(answer.answer, "回答")
        self.assertEqual(rag_service.system_prompt, "Use strict citations.")
        runs = [item for item in session.added if isinstance(item, ChatRun)]
        self.assertEqual(runs[0].prompt_version_id, 42)


if __name__ == "__main__":
    unittest.main()
