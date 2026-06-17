from __future__ import annotations

import unittest
from unittest.mock import patch

from app.retrieval.ingest import delete_documents_by_source


class FakeVectorStore:
    def __init__(self, ids_by_source: dict[str, list[str]]) -> None:
        self.ids_by_source = ids_by_source
        self.deleted_batches: list[list[str]] = []

    def get(self, *, where=None, include=None):
        return {"ids": self.ids_by_source.get(where["source"], [])}

    def delete(self, *, ids: list[str]) -> None:
        self.deleted_batches.append(list(ids))


class DeleteDocumentsBySourceTests(unittest.TestCase):
    def test_delete_source_normalizes_relative_path(self) -> None:
        vector_store = FakeVectorStore({"nested/source.txt": ["chunk-1", "chunk-2"]})

        with patch("app.retrieval.ingest.get_vector_store", return_value=vector_store):
            deleted = delete_documents_by_source("nested/source.txt", data_dir="./data/raw")

        self.assertEqual(deleted, 2)
        self.assertEqual(vector_store.deleted_batches, [["chunk-1", "chunk-2"]])

    def test_delete_source_skips_delete_when_no_chunks_match(self) -> None:
        vector_store = FakeVectorStore({})

        with patch("app.retrieval.ingest.get_vector_store", return_value=vector_store):
            deleted = delete_documents_by_source("missing.txt", data_dir="./data/raw")

        self.assertEqual(deleted, 0)
        self.assertEqual(vector_store.deleted_batches, [])

    def test_delete_source_rejects_empty_source(self) -> None:
        with self.assertRaises(ValueError):
            delete_documents_by_source("  ")


if __name__ == "__main__":
    unittest.main()
