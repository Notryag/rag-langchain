from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from app.config.logging_setup import setup_logging

DEFAULT_TRACE_OUTPUT_PATH = Path("storage/exports/chat_trace.json")

# Stable top-level fields for replay/debugging.
TRACE_FIELDS = {
    "query": "Original user query.",
    "thread_id": "Conversation thread id used for the run.",
    "answer": "Final assistant answer text.",
    "elapsed_ms": "End-to-end elapsed time in milliseconds.",
    "usage": "Token usage metadata returned by the model when available.",
    "tool_events": "Tool outputs including retrieved context and parsed citations.",
    "citations": "Deduplicated citations collected from tool events.",
    "status_lines": "User-facing status updates collected during the run.",
}


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for citation in citations:
        key = (
            citation.get("rank"),
            citation.get("source"),
            citation.get("page"),
            citation.get("chunk_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique


def capture_chat_trace(query: str, *, thread_id: str | None = None) -> dict[str, Any]:
    from app.services.chat_client import get_chat_client, new_thread_id

    client = get_chat_client()
    resolved_thread_id = thread_id or new_thread_id("trace")
    started_at = time.perf_counter()

    answer_parts: list[str] = []
    tool_events: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    status_lines: list[str] = []
    usage: dict[str, Any] | None = None

    for event in client.stream(query, thread_id=resolved_thread_id):
        if event.type == "messages-tuple":
            event_type = event.data.get("type")
            if event_type == "ai":
                tool_calls = event.data.get("tool_calls") or []
                if tool_calls:
                    for tool_call in tool_calls:
                        status_lines.append(f"调用工具 {tool_call.get('name')}")
                    continue

                content = event.data.get("content", "")
                if content:
                    answer_parts.append(content)
                continue

            if event_type == "tool":
                status_lines.append(f"{event.data.get('name')} 已返回结果")
                tool_citations = event.data.get("citations") or []
                citations.extend(tool_citations)
                tool_events.append(
                    {
                        "name": event.data.get("name"),
                        "tool_call_id": event.data.get("tool_call_id"),
                        "content": event.data.get("content", ""),
                        "citations": tool_citations,
                    }
                )
                continue

        if event.type == "end":
            usage = event.data.get("usage")

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return {
        "query": query,
        "thread_id": resolved_thread_id,
        "answer": "".join(answer_parts),
        "elapsed_ms": elapsed_ms,
        "usage": usage,
        "tool_events": tool_events,
        "citations": _dedupe_citations(citations),
        "status_lines": status_lines,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture a single chat trace for replay/debugging.")
    parser.add_argument("query", help="User query to run through the agent.")
    parser.add_argument("--output", default=str(DEFAULT_TRACE_OUTPUT_PATH), help="Path to trace json output.")
    parser.add_argument("--thread-id", default=None, help="Optional thread id override.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging()

    trace = capture_chat_trace(args.query, thread_id=args.thread_id)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "trace_fields": TRACE_FIELDS,
                "trace": trace,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    print(f"trace_written={output_path.as_posix()}")


if __name__ == "__main__":
    main()
