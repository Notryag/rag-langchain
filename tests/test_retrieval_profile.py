from __future__ import annotations

import unittest

from app.retrieval.formatter import format_retrieved_chunks
from app.retrieval.profile import RetrievalProfile
from app.retrieval.retriever import RetrievedChunk
from app.retrieval.types import RetrievedChunk as BaseRetrievedChunk
from app.tools.retrieve_context import _profile_from_runtime


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

    def test_legacy_retrieved_chunk_is_unified_dto(self) -> None:
        chunk = RetrievedChunk(
            rank=1,
            content="content",
            document_id="doc-1",
            source="source.txt",
            page="2",
            chunk_index=3,
            metadata={},
        )

        self.assertIsInstance(chunk, BaseRetrievedChunk)
        self.assertEqual(chunk.to_reference()["filename"], "source.txt")

    def test_tool_profile_uses_runtime_context(self) -> None:
        class Runtime:
            context = {
                "retrieval_profile": {
                    "search_type": "hybrid",
                    "top_k": 2,
                    "fetch_k": 6,
                    "reranker_enabled": True,
                    "max_context_chars": 900,
                }
            }

        profile = _profile_from_runtime(Runtime())

        self.assertEqual(profile.search_type, "hybrid")
        self.assertEqual(profile.top_k, 2)
        self.assertEqual(profile.fetch_k, 6)
        self.assertTrue(profile.reranker_enabled)
        self.assertEqual(profile.max_context_chars, 900)


if __name__ == "__main__":
    unittest.main()
