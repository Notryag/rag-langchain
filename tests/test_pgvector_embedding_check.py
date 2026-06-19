from __future__ import annotations

import unittest

from evaluation.check_pgvector_embedding_config import _collect_issues


class PgVectorEmbeddingCheckTests(unittest.TestCase):
    def test_collect_issues_accepts_matching_config_and_database_dimensions(self) -> None:
        issues = _collect_issues(configured_dimension=1536, database_dimension=1536, actual_dimension=None)

        self.assertEqual(issues, [])

    def test_collect_issues_reports_database_mismatch(self) -> None:
        issues = _collect_issues(configured_dimension=1536, database_dimension=1024, actual_dimension=None)

        self.assertIn("Database vector dimension 1024", issues[0])

    def test_collect_issues_reports_actual_model_mismatch(self) -> None:
        issues = _collect_issues(configured_dimension=1536, database_dimension=1536, actual_dimension=1024)

        self.assertIn("Actual embedding model output dimension 1024", issues[0])

    def test_collect_issues_reports_unknown_database_dimension(self) -> None:
        issues = _collect_issues(configured_dimension=1536, database_dimension=None, actual_dimension=None)

        self.assertIn("Could not detect", issues[0])


if __name__ == "__main__":
    unittest.main()
