from __future__ import annotations

import logging
from functools import lru_cache
from uuid import uuid4

from app.agent.create_agent import build_agent

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_agent():
    logger.info("初始化共享 Agent 实例。")
    return build_agent()


def new_thread_id(prefix: str = "chat") -> str:
    return f"{prefix}_{uuid4().hex}"


def build_thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _stringify_content(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)

    return str(content)


def ask(user_input: str, thread_id: str) -> str:
    logger.info("收到聊天请求。thread_id=%s chars=%s", thread_id, len(user_input))
    agent = get_agent()
    config = build_thread_config(thread_id)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
    )
    final_msg = result["messages"][-1]
    answer = _stringify_content(final_msg.content)
    logger.info("聊天请求完成。thread_id=%s answer_chars=%s", thread_id, len(answer))
    return answer
