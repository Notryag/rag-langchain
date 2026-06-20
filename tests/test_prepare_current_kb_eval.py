from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.prepare_current_kb_eval import _expected_source_names


class PrepareCurrentKbEvalTests(unittest.TestCase):
    def test_expected_source_names_are_unique_and_sorted(self) -> None:
        with TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "retrieval.jsonl"
            dataset_path.write_text(
                "\n".join(
                    [
                        '{"id":"1","query":"q1","expected_sources":["b.txt","a.txt"]}',
                        '{"id":"2","query":"q2","expected_sources":["a.txt"]}',
                        '{"id":"3","query":"q3","expected_sources":[]}',
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(_expected_source_names(dataset_path), ["a.txt", "b.txt"])


if __name__ == "__main__":
    unittest.main()
