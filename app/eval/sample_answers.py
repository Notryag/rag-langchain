from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config.logging_setup import setup_logging
from app.eval.dataset import DEFAULT_ANSWER_EVAL_PATH, load_answer_eval_samples
from app.services.rag_service import get_rag_service, new_thread_id

DEFAULT_OUTPUT_PATH = Path("storage/exports/answer_eval_runs.jsonl")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample model answers for the answer eval dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_ANSWER_EVAL_PATH), help="Path to answer eval jsonl.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to output run jsonl.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N samples.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging()

    samples = load_answer_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rag_service = get_rag_service()

    with output_path.open("w", encoding="utf-8") as fh:
        for sample in samples:
            thread_id = new_thread_id("eval")
            result = rag_service.ask(sample.query, thread_id=thread_id)
            record = {
                "id": sample.id,
                "query": sample.query,
                "category": sample.category,
                "thread_id": result.thread_id,
                "answer": result.answer,
                "elapsed_ms": result.elapsed_ms,
                "usage": result.usage,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[OK] {sample.id} -> {output_path.as_posix()}")


if __name__ == "__main__":
    main()
