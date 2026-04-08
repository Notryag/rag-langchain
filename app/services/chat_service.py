from __future__ import annotations

from app.services.rag_service import get_rag_service


def get_agent():
    return get_rag_service().agent


def ask(user_input: str, thread_id: str) -> str:
    return get_rag_service().ask(user_input, thread_id=thread_id).answer
