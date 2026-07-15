from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.run_pgvector_baseline import (
    build_baseline_commands,
    build_baseline_paths,
    collect_baseline_summary,
    write_baseline_manifest,
)


class PgVectorBaselineRunnerTests(unittest.TestCase):
    def test_build_baseline_paths_keeps_artifacts_in_run_dir(self) -> None:
        paths = build_baseline_paths(Path("storage/exports/pgvector_baselines"), run_id="run-1")

        self.assertEqual(paths.run_dir.as_posix(), "storage/exports/pgvector_baselines/run-1")
        self.assertEqual(paths.answer_runs.parent, paths.run_dir)
        self.assertEqual(paths.manifest.parent, paths.run_dir)

    def test_build_baseline_commands_wires_pgvector_eval_steps(self) -> None:
        paths = build_baseline_paths(Path("out"), run_id="run-1")

        commands = build_baseline_commands(
            paths=paths,
            user_id=1,
            kb_id=2,
            retrieval_limit=3,
            answer_limit=4,
        )

        self.assertEqual(len(commands), 3)
        self.assertIn("evaluation.evaluate_pgvector_retrieval", commands[0])
        self.assertIn("--search-type", commands[0])
        self.assertIn("hybrid", commands[0])
        self.assertIn("--reranker", commands[0])
        self.assertIn("on", commands[0])
        self.assertIn("evaluation.generate_pgvector_answers", commands[1])
        self.assertIn(str(paths.answer_runs), commands[1])
        self.assertIn("evaluation.evaluate_answers", commands[2])
        self.assertIn(str(paths.answer_bad_cases), commands[2])
        self.assertIn(str(paths.answer_summary), commands[2])

    def test_build_baseline_commands_can_skip_answer_steps(self) -> None:
        paths = build_baseline_paths(Path("out"), run_id="run-1")

        commands = build_baseline_commands(
            paths=paths,
            user_id=1,
            kb_id=2,
            retrieval_limit=3,
            answer_limit=4,
            skip_answer=True,
        )

        self.assertEqual(len(commands), 1)
        self.assertIn("evaluation.evaluate_pgvector_retrieval", commands[0])

    def test_build_baseline_commands_can_use_custom_datasets(self) -> None:
        paths = build_baseline_paths(Path("out"), run_id="run-1")

        commands = build_baseline_commands(
            paths=paths,
            user_id=1,
            kb_id=2,
            retrieval_dataset="data/eval/customer_retrieval.jsonl",
            answer_dataset="data/eval/customer_answer.jsonl",
            retrieval_limit=None,
            answer_limit=None,
        )

        self.assertIn("--dataset", commands[0])
        self.assertIn("data/eval/customer_retrieval.jsonl", commands[0])
        self.assertIn("--dataset", commands[1])
        self.assertIn("data/eval/customer_answer.jsonl", commands[1])
        self.assertIn("--dataset", commands[2])
        self.assertIn("data/eval/customer_answer.jsonl", commands[2])

    def test_write_baseline_manifest_records_commands_and_artifacts(self) -> None:
        with TemporaryDirectory() as tmpdir:
            paths = build_baseline_paths(Path(tmpdir), run_id="run-1")
            commands = [["python", "-m", "evaluation.evaluate_pgvector_retrieval"]]

            write_baseline_manifest(paths, run_id="run-1", user_id=1, kb_id=2, commands=commands)

            payload = json.loads(paths.manifest.read_text(encoding="utf-8"))

        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["kb_id"], 2)
        self.assertEqual(payload["commands"], commands)
        self.assertIn("answer_bad_cases", payload["artifacts"])
        self.assertIn("answer_summary", payload["artifacts"])

    def test_collect_baseline_summary_counts_artifacts(self) -> None:
        with TemporaryDirectory() as tmpdir:
            paths = build_baseline_paths(Path(tmpdir), run_id="run-1")
            paths.run_dir.mkdir(parents=True)
            paths.answer_runs.write_text("{}\n{}\n", encoding="utf-8")
            paths.answer_bad_cases.write_text("{}\n", encoding="utf-8")
            paths.answer_summary.write_text('{"pass_rate": 0.5}', encoding="utf-8")
            paths.retrieval_bad_cases.write_text("{}\n{}\n{}\n", encoding="utf-8")
            (paths.run_dir / "pgvector_retrieval_manifest_similarity_reranker_off.json").write_text(
                '{"summary":{"passed":1}}',
                encoding="utf-8",
            )

            summary = collect_baseline_summary(paths)

        self.assertEqual(summary["retrieval_manifest_count"], 1)
        self.assertEqual(summary["answer_run_count"], 2)
        self.assertEqual(summary["answer_bad_case_count"], 1)
        self.assertEqual(summary["retrieval_bad_case_count"], 3)
        self.assertEqual(summary["retrieval_summaries"][0]["passed"], 1)
        self.assertEqual(summary["answer_summary"]["pass_rate"], 0.5)

    def test_write_baseline_manifest_can_record_failed_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            paths = build_baseline_paths(Path(tmpdir), run_id="run-1")

            write_baseline_manifest(
                paths,
                run_id="run-1",
                user_id=1,
                kb_id=2,
                commands=[["python"]],
                status="failed",
                summary={"error": {"returncode": 1}},
            )

            payload = json.loads(paths.manifest.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["summary"]["error"]["returncode"], 1)


if __name__ == "__main__":
    unittest.main()
