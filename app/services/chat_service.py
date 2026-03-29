from __future__ import annotations

from app.services.chat_client import build_thread_config, get_chat_client, new_thread_id


def get_agent():
    return get_chat_client().agent


def ask(user_input: str, thread_id: str) -> str:
    return get_chat_client().ask(user_input, thread_id).answer
