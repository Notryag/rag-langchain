from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document as LangChainDocument

from app.config.settings import settings
from app.retrieval.pgvector_store import (
    ingest_document_chunks,
    retrieve_pgvector_chunks,
    retrieve_pgvector_hybrid_chunks,
    retrieve_pgvector_lexical_chunks,
    retrieve_pgvector_retrieved_chunks,
    rerank_pgvector_chunks,
)


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 0.1] for index, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [0.2] * settings.embedding_dimension


class WrongDimensionEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [0.2, 0.3]


class FakeSession:
    def __init__(self, execute_result=None) -> None:
        self.added = []
        self.executed = []
        self.commits = 0
        self.execute_result = execute_result or []

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def execute(self, statement):
        self.executed.append(statement)
        if callable(self.execute_result):
            return self.execute_result(statement)
        return self.execute_result


class PgVectorStoreTests(unittest.TestCase):
    def test_ingest_document_chunks_replaces_existing_chunks(self) -> None:
        session = FakeSession()
        document = SimpleNamespace(id=9, kb_id=3, user_id=2, filename="manual.txt")
        parsed_docs = [LangChainDocument(page_content="hello world", metadata={"page": 1})]

        count = ingest_document_chunks(
            session,
            document=document,
            parsed_docs=parsed_docs,
            embeddings=FakeEmbeddings(),
        )

        self.assertEqual(count, 1)
        self.assertEqual(len(session.added), 1)
        self.assertEqual(session.commits, 1)
        self.assertEqual(len(session.executed), 1)
        chunk = session.added[0]
        self.assertEqual(chunk.document_id, 9)
        self.assertEqual(chunk.kb_id, 3)
        self.assertEqual(chunk.user_id, 2)
        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(chunk.content, "hello world")
        self.assertEqual(chunk.embedding, [0.0, 0.1])
        self.assertEqual(chunk.chunk_metadata["source"], "manual.txt")
        self.assertEqual(chunk.chunk_metadata["document_id"], 9)

    def test_retrieve_pgvector_chunks_returns_references_with_tenant_filter(self) -> None:
        chunk = SimpleNamespace(
            id=7,
            document_id=9,
            chunk_index=2,
            content="计费规则包括调用次数",
            chunk_metadata={"page": 1},
        )
        session = FakeSession(execute_result=[(chunk, "产品说明.pdf", 0.12)])

        results = retrieve_pgvector_chunks(
            session,
            user_id=2,
            kb_id=3,
            query="怎么计费",
            top_k=5,
            embeddings=FakeEmbeddings(),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].to_reference()["filename"], "产品说明.pdf")
        self.assertEqual(results[0].to_reference()["chunk_id"], 7)
        statement_text = str(session.executed[0])
        self.assertIn("document_chunks.user_id", statement_text)
        self.assertIn("document_chunks.kb_id", statement_text)

    def test_retrieve_pgvector_chunks_fails_fast_on_embedding_dimension_mismatch(self) -> None:
        session = FakeSession()

        with self.assertRaisesRegex(ValueError, "Embedding dimension mismatch"):
            retrieve_pgvector_chunks(
                session,
                user_id=2,
                kb_id=3,
                query="怎么计费",
                top_k=5,
                embeddings=WrongDimensionEmbeddings(),
            )

        self.assertEqual(session.executed, [])

    def test_retrieve_pgvector_chunks_supports_mmr_with_fetched_candidates(self) -> None:
        dimension = settings.embedding_dimension
        query_embedding = [1.0] + [0.0] * (dimension - 1)
        candidate_embeddings = [
            [0.94, 0.342] + [0.0] * (dimension - 2),
            [0.906, 0.423] + [0.0] * (dimension - 2),
            [0.643, -0.766] + [0.0] * (dimension - 2),
        ]
        chunks = [
            SimpleNamespace(
                id=index,
                document_id=9,
                chunk_index=index,
                content=f"候选 {index}",
                chunk_metadata={},
                embedding=candidate_embeddings[index - 1],
            )
            for index in range(1, 4)
        ]
        session = FakeSession(
            execute_result=[(chunk, f"{chunk.id}.pdf", float(chunk.id) / 10) for chunk in chunks]
        )

        results = retrieve_pgvector_chunks(
            session,
            user_id=2,
            kb_id=3,
            query="怎么计费",
            top_k=2,
            fetch_k=3,
            search_type="mmr",
            embeddings=SimpleNamespace(embed_query=lambda _: query_embedding),
        )

        self.assertEqual([chunk.chunk_id for chunk in results], [1, 3])
        self.assertEqual(session.executed[0]._limit_clause.value, 3)

    def test_retrieve_pgvector_retrieved_chunks_returns_unified_dto(self) -> None:
        chunk = SimpleNamespace(
            id=7,
            document_id=9,
            chunk_index=2,
            content="计费规则包括调用次数",
            chunk_metadata={"page": 1},
        )
        session = FakeSession(execute_result=[(chunk, "产品说明.pdf", 0.12)])

        results = retrieve_pgvector_retrieved_chunks(
            session,
            user_id=2,
            kb_id=3,
            query="怎么计费",
            top_k=5,
            embeddings=FakeEmbeddings(),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rank, 1)
        self.assertEqual(results[0].source, "产品说明.pdf")
        self.assertEqual(results[0].document_id, 9)
        self.assertEqual(results[0].chunk_id, 7)
        self.assertEqual(results[0].chunk_index, 2)
        self.assertEqual(results[0].score, 0.12)
        self.assertEqual(results[0].to_reference()["filename"], "产品说明.pdf")

    def test_retrieve_pgvector_lexical_chunks_filters_by_tenant_and_scores_content(self) -> None:
        matching_chunk = SimpleNamespace(
            id=7,
            document_id=9,
            chunk_index=2,
            content="计费规则包括调用次数",
            chunk_metadata={"user_id": 2, "kb_id": 3},
        )
        session = FakeSession(execute_result=[(matching_chunk, "产品说明.pdf", 4)])

        results = retrieve_pgvector_lexical_chunks(
            session,
            user_id=2,
            kb_id=3,
            query="怎么计费",
            top_k=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, 7)
        self.assertEqual(results[0].metadata["lexical_score"], 4)
        statement_text = str(session.executed[0])
        self.assertIn("document_chunks.user_id", statement_text)
        self.assertIn("document_chunks.kb_id", statement_text)
        self.assertIn("LIKE", statement_text)
        self.assertEqual(session.executed[0]._limit_clause.value, 5)

    def test_retrieve_pgvector_lexical_chunks_skips_queries_without_trigrams(self) -> None:
        session = FakeSession()

        results = retrieve_pgvector_lexical_chunks(session, user_id=2, kb_id=3, query="X1", top_k=5)

        self.assertEqual(results, [])
        self.assertEqual(session.executed, [])

    def test_retrieve_pgvector_hybrid_chunks_fuses_dense_and_lexical_candidates(self) -> None:
        dense_chunk = SimpleNamespace(
            id=7,
            document_id=9,
            chunk_index=2,
            content="向量命中",
            chunk_metadata={"user_id": 2, "kb_id": 3},
        )
        lexical_chunk = SimpleNamespace(
            id=8,
            document_id=10,
            chunk_index=1,
            content="计费规则包括调用次数",
            chunk_metadata={"user_id": 2, "kb_id": 3},
        )

        calls = []

        def execute_result(statement):
            calls.append(str(statement))
            if len(calls) == 1:
                return [(dense_chunk, "dense.pdf", 0.11)]
            return [(lexical_chunk, "lexical.pdf", 4)]

        session = FakeSession(execute_result=execute_result)

        results = retrieve_pgvector_hybrid_chunks(
            session,
            user_id=2,
            kb_id=3,
            query="怎么计费",
            top_k=2,
            fetch_k=4,
            embeddings=FakeEmbeddings(),
        )

        self.assertEqual([chunk.filename for chunk in results], ["dense.pdf", "lexical.pdf"])
        self.assertEqual(len(session.executed), 2)

    def test_rerank_pgvector_chunks_preserves_original_chunk_payloads(self) -> None:
        first = SimpleNamespace(
            chunk_id=7,
            document_id=9,
            filename="first.pdf",
            chunk_index=1,
            content="一般内容",
            metadata={"user_id": 2, "kb_id": 3},
            distance=0.1,
        )
        second = SimpleNamespace(
            chunk_id=8,
            document_id=10,
            filename="second.pdf",
            chunk_index=1,
            content="计费规则包括调用次数",
            metadata={"user_id": 2, "kb_id": 3},
            distance=0.2,
        )

        def fake_rerank(query, documents, *, top_k):
            return [documents[1], documents[0]][:top_k]

        with patch("app.retrieval.pgvector_store.rerank_documents", side_effect=fake_rerank):
            results = rerank_pgvector_chunks("怎么计费", [first, second], top_k=2)

        self.assertEqual([chunk.filename for chunk in results], ["second.pdf", "first.pdf"])

    def test_retrieve_pgvector_chunks_fetches_candidates_before_rerank(self) -> None:
        chunks = [
            SimpleNamespace(
                id=7,
                document_id=9,
                chunk_index=1,
                content="第一",
                chunk_metadata={"user_id": 2, "kb_id": 3},
            ),
            SimpleNamespace(
                id=8,
                document_id=10,
                chunk_index=1,
                content="第二",
                chunk_metadata={"user_id": 2, "kb_id": 3},
            ),
        ]
        session = FakeSession(execute_result=[(chunks[0], "first.pdf", 0.1), (chunks[1], "second.pdf", 0.2)])

        def fake_rerank(query, documents, *, top_k):
            return [documents[1]]

        with patch("app.retrieval.pgvector_store.rerank_documents", side_effect=fake_rerank):
            results = retrieve_pgvector_chunks(
                session,
                user_id=2,
                kb_id=3,
                query="怎么计费",
                top_k=1,
                fetch_k=2,
                reranker_enabled=True,
                embeddings=FakeEmbeddings(),
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].filename, "second.pdf")


if __name__ == "__main__":
    unittest.main()
