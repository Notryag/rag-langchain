from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from langchain_core.documents import Document

from app.retrieval.reranker import rerank_documents


class RerankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = [
            Document(page_content="first", metadata={"source": "first.txt"}),
            Document(page_content="second", metadata={"source": "second.txt"}),
            Document(page_content="third", metadata={"source": "third.txt"}),
        ]

    def test_http_reranker_uses_returned_document_indices(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["authorization"], "Bearer reranker-key")
            self.assertIn('"top_n":2', request.content.decode().replace(" ", ""))
            return httpx.Response(200, json=[{"index": 2, "score": 0.9}, {"index": 0, "score": 0.4}])

        client = httpx.Client(transport=httpx.MockTransport(handler))
        configured_settings = SimpleNamespace(
            reranker_strategy="http",
            reranker_api_url="https://reranker.test/rerank",
            reranker_api_key="reranker-key",
            reranker_model="bge-reranker-v2-m3",
        )
        with (
            client,
            patch("app.retrieval.reranker.settings", configured_settings),
            patch("app.retrieval.reranker._get_http_client", return_value=client),
        ):
            results = rerank_documents("query", self.documents, top_k=2, strategy="http")

        self.assertEqual([document.page_content for document in results], ["third", "first"])

    def test_http_reranker_falls_back_after_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        configured_settings = SimpleNamespace(
            reranker_strategy="http",
            reranker_api_url="https://reranker.test/rerank",
            reranker_api_key=None,
            reranker_model=None,
        )
        with (
            client,
            patch("app.retrieval.reranker.settings", configured_settings),
            patch("app.retrieval.reranker._get_http_client", return_value=client),
            patch(
                "app.retrieval.reranker._rerank_via_embedding_lexical",
                return_value=[self.documents[1]],
            ) as fallback,
        ):
            results = rerank_documents("query", self.documents, top_k=1, strategy="http")

        self.assertEqual(results, [self.documents[1]])
        fallback.assert_called_once()

    def test_http_reranker_rejects_invalid_indices_and_falls_back(self) -> None:
        client = httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [{"index": 99}]}))
        )
        configured_settings = SimpleNamespace(
            reranker_strategy="http",
            reranker_api_url="https://reranker.test/rerank",
            reranker_api_key=None,
            reranker_model=None,
        )
        with (
            client,
            patch("app.retrieval.reranker.settings", configured_settings),
            patch("app.retrieval.reranker._get_http_client", return_value=client),
            patch("app.retrieval.reranker._rerank_via_embedding_lexical", return_value=[]) as fallback,
        ):
            results = rerank_documents("query", self.documents, top_k=1, strategy="http")

        self.assertEqual(results, [])
        fallback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
