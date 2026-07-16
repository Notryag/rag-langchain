from __future__ import annotations

import math
import re
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from langchain_core.documents import Document

from app.config.settings import settings
from app.retrieval.embeddings import get_embeddings

_SUPPORTED_RERANKER_STRATEGIES = {"embedding_lexical", "http"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_EMBEDDING_WEIGHT = 0.85
_LEXICAL_WEIGHT = 0.15
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankedDocument:
    rank: int
    score: float
    lexical_score: float
    embedding_score: float
    document: Document


def normalize_reranker_strategy(strategy: str | None = None) -> str:
    resolved = (strategy or settings.reranker_strategy).strip().lower()
    if resolved not in _SUPPORTED_RERANKER_STRATEGIES:
        supported = ", ".join(sorted(_SUPPORTED_RERANKER_STRATEGIES))
        raise ValueError(f"RERANKER_STRATEGY must be one of [{supported}], got: {resolved}")
    return resolved


def _tokenize(text: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(text)}
    return {token for token in tokens if len(token) > 1 or not token.isascii()}


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
    return dot / (left_norm * right_norm)


def _lexical_overlap_score(query: str, doc: Document) -> float:
    query_terms = _tokenize(query)
    if not query_terms:
        return 0.0

    metadata = doc.metadata or {}
    doc_text = " ".join(
        [
            doc.page_content,
            str(metadata.get("source", "")),
            str(metadata.get("page", "")),
        ]
    )
    doc_terms = _tokenize(doc_text)
    if not doc_terms:
        return 0.0

    return len(query_terms & doc_terms) / len(query_terms)


def rerank_documents(
    query: str,
    documents: list[Document],
    *,
    top_k: int,
    strategy: str | None = None,
) -> list[Document]:
    if not documents:
        return []

    resolved_strategy = normalize_reranker_strategy(strategy)
    if resolved_strategy == "http":
        try:
            return _rerank_via_http(query, documents, top_k=top_k)
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            logger.warning("HTTP reranker failed; falling back to embedding_lexical: %s", exc)

    return _rerank_via_embedding_lexical(query, documents, top_k=top_k)


def _rerank_via_embedding_lexical(query: str, documents: list[Document], *, top_k: int) -> list[Document]:
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)
    doc_vectors = embeddings.embed_documents([document.page_content for document in documents])

    scored_documents: list[RerankedDocument] = []
    for index, (document, doc_vector) in enumerate(zip(documents, doc_vectors, strict=False), start=1):
        embedding_score = _cosine_similarity(query_vector, doc_vector)
        lexical_score = _lexical_overlap_score(query, document)
        score = (_EMBEDDING_WEIGHT * embedding_score) + (_LEXICAL_WEIGHT * lexical_score)
        scored_documents.append(
            RerankedDocument(
                rank=index,
                score=score,
                lexical_score=lexical_score,
                embedding_score=embedding_score,
                document=document,
            )
        )

    reranked = sorted(scored_documents, key=lambda item: item.score, reverse=True)
    return [item.document for item in reranked[:top_k]]


def _rerank_via_http(query: str, documents: list[Document], *, top_k: int) -> list[Document]:
    if not settings.reranker_api_url:
        raise ValueError("RERANKER_API_URL is required for the HTTP reranker")

    payload: dict[str, Any] = {
        "query": query,
        "texts": [document.page_content for document in documents],
        "top_n": min(top_k, len(documents)),
    }
    if settings.reranker_model:
        payload["model"] = settings.reranker_model

    headers = {"Accept": "application/json"}
    if settings.reranker_api_key:
        headers["Authorization"] = f"Bearer {settings.reranker_api_key}"

    response = _get_http_client().post(settings.reranker_api_url, json=payload, headers=headers)
    response.raise_for_status()
    return _documents_from_http_response(response.json(), documents, top_k=top_k)


def _documents_from_http_response(payload: Any, documents: list[Document], *, top_k: int) -> list[Document]:
    raw_results = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(raw_results, list):
        raise ValueError("HTTP reranker response must be a list or contain a results list")

    ranked_indices: list[int] = []
    seen: set[int] = set()
    for result in raw_results:
        if not isinstance(result, dict):
            raise ValueError("HTTP reranker result entries must be objects")
        index = result.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(documents):
            raise ValueError(f"HTTP reranker returned invalid document index: {index}")
        if index in seen:
            continue
        seen.add(index)
        ranked_indices.append(index)
        if len(ranked_indices) >= top_k:
            break

    if not ranked_indices:
        raise ValueError("HTTP reranker returned no ranked documents")
    return [documents[index] for index in ranked_indices]


@lru_cache(maxsize=1)
def _get_http_client() -> httpx.Client:
    return httpx.Client(timeout=settings.reranker_timeout_seconds)
