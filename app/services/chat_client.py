from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from textwrap import shorten
from typing import Any, Iterator, Literal
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.create_agent import build_agent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatEvent:
    kind: Literal["token", "status", "done"]
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResult:
    answer: str
    usage: dict[str, Any] | None = None
    elapsed_ms: int | None = None


def new_thread_id(prefix: str = "chat") -> str:
    return f"{prefix}_{uuid4().hex}"


def build_thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _stringify_content(content: Any) -> str:
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


def _normalize_user_input(text: str) -> str:
    normalized = text.encode("utf-8", errors="replace").decode("utf-8")
    if normalized != text:
        logger.warning("检测到不可编码字符，已使用替代字符归一化输入。")
    return normalized


class AgentChatClient:
    def __init__(self) -> None:
        logger.info("初始化共享 Agent 实例。")
        self._agent = build_agent()

    @property
    def agent(self):
        return self._agent

    def ask(self, user_input: str, thread_id: str) -> ChatResult:
        user_input = _normalize_user_input(user_input)
        logger.info("收到聊天请求。thread_id=%s chars=%s", thread_id, len(user_input))
        started_at = time.perf_counter()
        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=build_thread_config(thread_id),
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        final_msg = result["messages"][-1]
        answer = _stringify_content(final_msg.content)
        usage = getattr(final_msg, "usage_metadata", None)
        logger.info(
            "聊天请求完成。thread_id=%s answer_chars=%s elapsed_ms=%s",
            thread_id,
            len(answer),
            elapsed_ms,
        )
        return ChatResult(answer=answer, usage=usage, elapsed_ms=elapsed_ms)

    def stream(self, user_input: str, thread_id: str) -> Iterator[ChatEvent]:
        user_input = _normalize_user_input(user_input)
        logger.info("开始流式聊天。thread_id=%s chars=%s", thread_id, len(user_input))
        started_at = time.perf_counter()
        answer_parts: list[str] = []
        usage: dict[str, Any] | None = None
        seen_tool_calls: set[str] = set()
        seen_tool_results: set[str] = set()

        for mode, payload in self._agent.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            config=build_thread_config(thread_id),
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                message_chunk, metadata = payload
                if metadata.get("langgraph_node") != "model":
                    continue

                text = _stringify_content(getattr(message_chunk, "content", message_chunk))
                if not text:
                    continue

                answer_parts.append(text)
                yield ChatEvent(
                    kind="token",
                    text=text,
                    metadata={
                        "node": metadata.get("langgraph_node"),
                        "step": metadata.get("langgraph_step"),
                    },
                )
                continue

            if mode != "updates":
                continue

            for node_name, node_data in payload.items():
                for message in node_data.get("messages", []):
                    if isinstance(message, AIMessage):
                        tool_calls = getattr(message, "tool_calls", []) or []
                        if tool_calls:
                            for tool_call in tool_calls:
                                call_id = tool_call.get("id") or f"{tool_call.get('name')}:{tool_call.get('args')}"
                                if call_id in seen_tool_calls:
                                    continue
                                seen_tool_calls.add(call_id)
                                tool_name = tool_call.get("name", "tool")
                                yield ChatEvent(
                                    kind="status",
                                    text=f"调用工具 {tool_name}",
                                    metadata={
                                        "node": node_name,
                                        "tool_name": tool_name,
                                        "args": tool_call.get("args", {}),
                                    },
                                )
                        else:
                            usage = getattr(message, "usage_metadata", None) or usage
                        continue

                    if isinstance(message, ToolMessage):
                        result_key = message.tool_call_id or message.id
                        if result_key in seen_tool_results:
                            continue
                        seen_tool_results.add(result_key)
                        preview = shorten(
                            _stringify_content(message.content).replace("\n", " "),
                            width=120,
                            placeholder="...",
                        )
                        # 每产生一个数据，就立刻把它丢给调用者
                        yield ChatEvent(
                            kind="status",
                            text=f"{message.name or 'tool'} 已返回结果",
                            metadata={
                                "node": node_name,
                                "tool_name": message.name or "tool",
                                "preview": preview,
                            },
                        )

        answer = "".join(answer_parts)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "流式聊天完成。thread_id=%s answer_chars=%s elapsed_ms=%s",
            thread_id,
            len(answer),
            elapsed_ms,
        )
        yield ChatEvent(
            kind="done",
            metadata={
                "answer": answer,
                "usage": usage,
                "elapsed_ms": elapsed_ms,
            },
        )


@lru_cache(maxsize=1)
def get_chat_client() -> AgentChatClient:
    return AgentChatClient()
