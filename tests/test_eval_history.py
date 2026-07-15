from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.history import append_history_record, load_history


class EvaluationHistoryTests(unittest.TestCase):
    def test_history_is_append_only_jsonl(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.jsonl"
            append_history_record(path, {"run_id": "one", "status": "completed"})
            append_history_record(path, {"run_id": "two", "status": "failed"})

            self.assertEqual([item["run_id"] for item in load_history(path)], ["one", "two"])
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)
            json.loads(path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
