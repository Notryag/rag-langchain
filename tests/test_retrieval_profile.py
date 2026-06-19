from __future__ import annotations

import unittest

from app.retrieval.formatter import format_retrieved_chunks
from app.retrieval.profile import RetrievalProfile
from app.retrieval.types import RetrievedChunk


class RetrievalProfileTests(unittest.TestCase):
    def test_normalizes_search_type_and_fetch_k_override(self) -> None:
        profile = RetrievalProfile(
            search_type="MMR",
            top_k=3,
            fetch_k=8,
            reranker_enabled=False,
            max_context_chars=1000,
        )

        updated = profile.with_overrides(top_k=5, fetch_k=2)

        self.assertEqual(profile.search_type, "mmr")
        self.assertEqual(updated.top_k, 5)
        self.assertEqual(updated.fetch_k, 5)

    def test_rejects_invalid_profile(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalProfile(
                search_type="bad",
                top_k=3,
                fetch_k=8,
                reranker_enabled=False,
                max_context_chars=1000,
            )

        with self.assertRaises(ValueError):
            RetrievalProfile(
                search_type="similarity",
                top_k=5,
                fetch_k=3,
                reranker_enabled=False,
                max_context_chars=1000,
            )

    def test_formatter_uses_context_budget(self) -> None:
        chunk = RetrievedChunk(
            rank=1,
            content="一" * 500,
            document_id="doc-1",
            source="source.txt",
            page=None,
            chunk_index=1,
            metadata={},
        )

        formatted = format_retrieved_chunks([chunk], max_context_chars=120)

        self.assertLessEqual(len(formatted), 140)
        self.assertIn("source=source.txt", formatted)

    def test_retrieved_chunk_reference_shape(self) -> None:
        chunk = RetrievedChunk(
            rank=1,
            content="content",
            document_id="doc-1",
            source="source.txt",
            page="2",
            chunk_index=3,
            metadata={},
        )

        self.assertEqual(chunk.to_reference()["filename"], "source.txt")


if __name__ == "__main__":
    unittest.main()
