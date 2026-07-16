from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from evaluation.dataset import DEFAULT_ANSWER_EVAL_PATH, DEFAULT_RETRIEVAL_EVAL_PATH
from evaluation.history import append_history_record, build_history_record
from evaluation.history import current_git_commit


DEFAULT_OUTPUT_DIR = Path("storage/exports/pgvector_baselines")


@dataclass(frozen=True)
class BaselinePaths:
    run_dir: Path
    retrieval_manifest: Path
    retrieval_bad_cases: Path
    answer_runs: Path
    answer_bad_cases: Path
    answer_summary: Path
    manifest: Path
    history: Path


def build_baseline_paths(output_dir: Path, *, run_id: str) -> BaselinePaths:
    run_dir = output_dir / run_id
    return BaselinePaths(
        run_dir=run_dir,
        retrieval_manifest=run_dir / "pgvector_retrieval_manifest.json",
        retrieval_bad_cases=run_dir / "pgvector_retrieval_bad_cases.jsonl",
        answer_runs=run_dir / "pgvector_answer_runs.jsonl",
        answer_bad_cases=run_dir / "pgvector_answer_bad_cases.jsonl",
        answer_summary=run_dir / "pgvector_answer_summary.json",
        manifest=run_dir / "baseline_manifest.json",
        history=output_dir / "history.jsonl",
    )


def build_baseline_commands(
    *,
    paths: BaselinePaths,
    user_id: int,
    kb_id: int,
    retrieval_dataset: str | None = None,
    answer_dataset: str | None = None,
    retrieval_limit: int | None,
    answer_limit: int | None,
    skip_answer: bool = False,
) -> list[list[str]]:
    retrieval_command = [
        sys.executable,
        "-m",
        "evaluation.evaluate_pgvector_retrieval",
        "--user-id",
        str(user_id),
        "--kb-id",
        str(kb_id),
        "--search-type",
        "similarity",
        "hybrid",
        "--reranker",
        "off",
        "on",
        "--bad-cases-out",
        str(paths.retrieval_bad_cases),
        "--manifest-output",
        str(paths.retrieval_manifest),
    ]
    if retrieval_dataset is not None:
        retrieval_command.extend(["--dataset", retrieval_dataset])
    if retrieval_limit is not None:
        retrieval_command.extend(["--limit", str(retrieval_limit)])

    answer_sampling_command = [
        sys.executable,
        "-m",
        "evaluation.generate_pgvector_answers",
        "--user-id",
        str(user_id),
        "--kb-id",
        str(kb_id),
        "--output",
        str(paths.answer_runs),
    ]
    if answer_dataset is not None:
        answer_sampling_command.extend(["--dataset", answer_dataset])
    if answer_limit is not None:
        answer_sampling_command.extend(["--limit", str(answer_limit)])

    answer_eval_command = [
        sys.executable,
        "-m",
        "evaluation.evaluate_answers",
        "--runs",
        str(paths.answer_runs),
        "--bad-cases-out",
        str(paths.answer_bad_cases),
        "--summary-output",
        str(paths.answer_summary),
    ]
    if answer_dataset is not None:
        answer_eval_command.extend(["--dataset", answer_dataset])
    if answer_limit is not None:
        answer_eval_command.extend(["--limit", str(answer_limit)])

    if skip_answer:
        return [retrieval_command]
    return [retrieval_command, answer_sampling_command, answer_eval_command]


def write_baseline_manifest(
    paths: BaselinePaths,
    *,
    run_id: str,
    user_id: int,
    kb_id: int,
    commands: list[list[str]],
    retrieval_dataset: str | None = None,
    answer_dataset: str | None = None,
    status: str = "planned",
    summary: dict | None = None,
) -> None:
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "user_id": user_id,
        "kb_id": kb_id,
        "git_commit": current_git_commit(),
        "runtime": {
            "python_version": platform.python_version(),
            "chat_model": os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "bge-m3"),
            "embedding_dimension": os.getenv("EMBEDDING_DIMENSION", "1024"),
        },
        "datasets": {
            "retrieval": _dataset_metadata(retrieval_dataset),
            "answer": _dataset_metadata(answer_dataset),
        },
        "commands": commands,
        "artifacts": {
            "retrieval_manifest_prefix": str(paths.retrieval_manifest),
            "retrieval_bad_cases": str(paths.retrieval_bad_cases),
            "answer_runs": str(paths.answer_runs),
            "answer_bad_cases": str(paths.answer_bad_cases),
            "answer_summary": str(paths.answer_summary),
        },
        "summary": summary or {},
    }
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    with paths.manifest.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _dataset_metadata(path: str | None) -> dict | None:
    if path is None:
        return None

    dataset_path = Path(path)
    metadata: dict[str, str | int | bool] = {
        "path": dataset_path.as_posix(),
        "exists": dataset_path.is_file(),
    }
    if not dataset_path.is_file():
        return metadata

    content = dataset_path.read_bytes()
    metadata.update(
        {
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
            "records": sum(1 for line in content.splitlines() if line.strip()),
        }
    )
    return metadata


def run_commands(commands: list[list[str]]) -> None:
    for command in commands:
        print("$ " + " ".join(command), flush=True)
        subprocess.run(command, check=True)


def collect_baseline_summary(paths: BaselinePaths) -> dict:
    retrieval_manifests = sorted(paths.run_dir.glob(f"{paths.retrieval_manifest.stem}_*.json"))
    answer_bad_cases = _count_jsonl_records(paths.answer_bad_cases)
    retrieval_bad_cases = _count_jsonl_records(paths.retrieval_bad_cases)
    return {
        "retrieval_manifest_count": len(retrieval_manifests),
        "retrieval_bad_case_count": retrieval_bad_cases,
        "answer_run_count": _count_jsonl_records(paths.answer_runs),
        "answer_bad_case_count": answer_bad_cases,
        "retrieval_summaries": [_read_json(path).get("summary", {}) for path in retrieval_manifests],
        "answer_summary": _read_json(paths.answer_summary) if paths.answer_summary.exists() else {},
    }


def _count_jsonl_records(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pgvector retrieval + answer evaluation baseline.")
    parser.add_argument("--user-id", type=int, required=True, help="Tenant user id used for pgvector eval.")
    parser.add_argument("--kb-id", type=int, required=True, help="Knowledge base id used for pgvector eval.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for baseline artifacts.")
    parser.add_argument("--run-id", default=None, help="Optional stable run id; defaults to UTC timestamp.")
    parser.add_argument("--retrieval-dataset", default=None, help="Path to retrieval eval jsonl.")
    parser.add_argument("--answer-dataset", default=None, help="Path to answer eval jsonl.")
    parser.add_argument("--retrieval-limit", type=int, default=None, help="Limit retrieval eval samples.")
    parser.add_argument("--answer-limit", type=int, default=None, help="Limit answer eval samples.")
    parser.add_argument("--skip-answer", action="store_true", help="Only run retrieval eval artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Only write manifest and print commands.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    retrieval_dataset = args.retrieval_dataset or str(DEFAULT_RETRIEVAL_EVAL_PATH)
    answer_dataset = args.answer_dataset or str(DEFAULT_ANSWER_EVAL_PATH)
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    paths = build_baseline_paths(Path(args.output_dir), run_id=run_id)
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    commands = build_baseline_commands(
        paths=paths,
        user_id=args.user_id,
        kb_id=args.kb_id,
        retrieval_dataset=retrieval_dataset,
        answer_dataset=answer_dataset,
        retrieval_limit=args.retrieval_limit,
        answer_limit=args.answer_limit,
        skip_answer=args.skip_answer,
    )
    write_baseline_manifest(
        paths,
        run_id=run_id,
        user_id=args.user_id,
        kb_id=args.kb_id,
        commands=commands,
        retrieval_dataset=retrieval_dataset,
        answer_dataset=answer_dataset,
    )
    print(f"baseline_manifest={paths.manifest.as_posix()}")
    if args.dry_run:
        for command in commands:
            print("$ " + " ".join(command))
        return
    try:
        run_commands(commands)
    except subprocess.CalledProcessError as exc:
        summary = collect_baseline_summary(paths)
        summary["error"] = {
            "returncode": exc.returncode,
            "command": exc.cmd,
            "traceback": traceback.format_exc(),
        }
        write_baseline_manifest(
            paths,
            run_id=run_id,
            user_id=args.user_id,
            kb_id=args.kb_id,
            commands=commands,
            retrieval_dataset=retrieval_dataset,
            answer_dataset=answer_dataset,
            status="failed",
            summary=summary,
        )
        append_history_record(
            paths.history,
            build_history_record(run_id=run_id, status="failed", user_id=args.user_id, kb_id=args.kb_id, summary=summary),
        )
        print(f"baseline_failed_manifest={paths.manifest.as_posix()}")
        raise
    else:
        summary = collect_baseline_summary(paths)
        write_baseline_manifest(
            paths,
            run_id=run_id,
            user_id=args.user_id,
            kb_id=args.kb_id,
            commands=commands,
            retrieval_dataset=retrieval_dataset,
            answer_dataset=answer_dataset,
            status="completed",
            summary=summary,
        )
        append_history_record(
            paths.history,
            build_history_record(run_id=run_id, status="completed", user_id=args.user_id, kb_id=args.kb_id, summary=summary),
        )
        print(f"baseline_summary={json.dumps(summary, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
