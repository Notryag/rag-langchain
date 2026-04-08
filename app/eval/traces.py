from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config.logging_setup import setup_logging
from app.retrieval.citations import Citation, citation_key
from app.services.rag_service import get_rag_service, new_thread_id

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


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[object, ...]] = set()
    unique: list[Citation] = []
    for citation in citations:
        key = citation_key(citation)
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique


def capture_chat_trace(query: str, *, thread_id: str | None = None) -> dict[str, Any]:
    rag_service = get_rag_service()
    resolved_thread_id = thread_id or new_thread_id("trace")
    tool_events: list[dict[str, Any]] = []
    final_result = None

    for event in rag_service.stream(query, thread_id=resolved_thread_id):
        if event.type == "tool_result":
            tool_events.append(
                {
                    "name": event.tool_name,
                    "content": event.content,
                    "citations": event.citations,
                }
            )
            continue

        if event.type == "complete":
            final_result = event.result

    if final_result is None:
        raise RuntimeError("Trace capture completed without a final result.")

    return {
        "query": query,
        "thread_id": final_result.thread_id,
        "answer": final_result.answer,
        "elapsed_ms": final_result.elapsed_ms,
        "usage": final_result.usage,
        "tool_events": tool_events,
        "citations": _dedupe_citations(final_result.citations),
        "status_lines": final_result.status_lines,
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
