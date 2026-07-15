from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.history import load_history
from evaluation.run_pgvector_baseline import DEFAULT_OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Show historical pgvector evaluation runs.")
    parser.add_argument("--history", default=str(DEFAULT_OUTPUT_DIR / "history.jsonl"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    records = load_history(Path(args.history))[-args.limit :]
    if args.as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    print("created_at\tstatus\tcommit\trun_id\tpass_rate\trecall\tcitation\tp95_ms\tcost_usd")
    for record in records:
        summary = record.get("summary", {})
        retrieval = summary.get("retrieval_summaries", [{}])
        retrieval_summary = retrieval[0] if retrieval else {}
        answer = summary.get("answer_summary", {})
        print("\t".join(str(value) for value in [
            record.get("created_at", ""), record.get("status", ""), record.get("git_commit") or "-",
            record.get("run_id", ""), answer.get("pass_rate", "-"), retrieval_summary.get("recall_at_k", "-"),
            answer.get("citation_accuracy", "-"), answer.get("p95_elapsed_ms", retrieval_summary.get("p95_latency_ms", "-")),
            answer.get("total_cost_usd", "-"),
        ]))


if __name__ == "__main__":
    main()
