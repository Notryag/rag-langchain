from __future__ import annotations

import unittest

from app.retrieval.types import RetrievedChunk
from evaluation.dataset import RetrievalEvalSample
from evaluation.evaluate_pgvector_retrieval import (
    PgVectorRetrievalEvalConfig,
    evaluate_pgvector_sample,
    result_to_bad_case,
    summarize,
)


def _sample(**overrides) -> RetrievalEvalSample:
    payload = {
        "id": "case_1",
        "query": "怎么计费？",
        "category": "billing",
        "expected_sources": ["产品说明.pdf"],
        "expected_keywords": ["调用次数", "存储容量"],
        "expected_min_keyword_hits": 2,
        "answerable": True,
        "score_retrieval": True,
    }
    payload.update(overrides)
    return RetrievalEvalSample.from_dict(payload)


def _chunk(**overrides) -> RetrievedChunk:
    payload = {
        "rank": 1,
        "content": "计费规则包括调用次数和存储容量。",
        "source": "产品说明.pdf",
        "document_id": 10,
        "chunk_id": 20,
        "chunk_index": 2,
        "metadata": {"user_id": 1, "kb_id": 2},
    }
    payload.update(overrides)
    return RetrievedChunk(**payload)


class PgVectorRetrievalEvalTests(unittest.TestCase):
    def test_evaluate_sample_passes_with_source_keywords_and_permission_scope(self) -> None:
        config = PgVectorRetrievalEvalConfig(
            user_id=1, kb_id=2, top_k=3, search_type="similarity", fetch_k=8, reranker_enabled=False
        )

        result = evaluate_pgvector_sample(_sample(), config, [_chunk()])

        self.assertTrue(result.passed)
        self.assertTrue(result.permission_ok)
        self.assertTrue(result.source_hit)
        self.assertEqual(result.matched_keywords, ["调用次数", "存储容量"])

    def test_evaluate_sample_fails_permission_leak_even_when_content_matches(self) -> None:
        config = PgVectorRetrievalEvalConfig(
            user_id=1, kb_id=2, top_k=3, search_type="similarity", fetch_k=8, reranker_enabled=False
        )

        result = evaluate_pgvector_sample(_sample(), config, [_chunk(metadata={"user_id": 9, "kb_id": 2})])

        self.assertFalse(result.passed)
        self.assertFalse(result.permission_ok)
        self.assertTrue(result.source_hit)

    def test_evaluate_sample_requires_explicit_tenant_metadata(self) -> None:
        config = PgVectorRetrievalEvalConfig(
            user_id=1, kb_id=2, top_k=3, search_type="similarity", fetch_k=8, reranker_enabled=False
        )

        result = evaluate_pgvector_sample(_sample(), config, [_chunk(metadata={})])

        self.assertFalse(result.passed)
        self.assertFalse(result.permission_ok)

    def test_bad_case_includes_references_and_tenant_config(self) -> None:
        config = PgVectorRetrievalEvalConfig(
            user_id=1, kb_id=2, top_k=3, search_type="hybrid", fetch_k=8, reranker_enabled=True
        )
        result = evaluate_pgvector_sample(_sample(), config, [_chunk(content="无关内容", source="其他.pdf")])

        payload = result_to_bad_case(result)

        self.assertEqual(payload["config"]["user_id"], 1)
        self.assertEqual(payload["config"]["kb_id"], 2)
        self.assertEqual(payload["config"]["search_type"], "hybrid")
        self.assertEqual(payload["config"]["fetch_k"], 8)
        self.assertTrue(payload["config"]["reranker_enabled"])
        self.assertFalse(payload["source_hit"])
        self.assertEqual(payload["references"][0]["filename"], "其他.pdf")

    def test_summarize_reports_permission_rate(self) -> None:
        config = PgVectorRetrievalEvalConfig(
            user_id=1, kb_id=2, top_k=3, search_type="similarity", fetch_k=8, reranker_enabled=False
        )
        results = [
            evaluate_pgvector_sample(_sample(id="pass"), config, [_chunk()]),
            evaluate_pgvector_sample(_sample(id="leak"), config, [_chunk(metadata={"user_id": 9, "kb_id": 2})]),
        ]

        summary = summarize(results)

        self.assertEqual(summary["scored"], 2)
        self.assertEqual(summary["permission_ok"], 1)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["permission_ok_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
