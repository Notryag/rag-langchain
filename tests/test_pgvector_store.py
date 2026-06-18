from __future__ import annotations

import unittest
from types import SimpleNamespace

from langchain_core.documents import Document as LangChainDocument

from app.retrieval.pgvector_store import ingest_document_chunks, retrieve_pgvector_chunks


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 0.1] for index, _ in enumerate(texts)]

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


if __name__ == "__main__":
    unittest.main()
