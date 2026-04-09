from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from app.config.settings import settings
from app.retrieval.normalizers import normalize_chunk_index, normalize_page, single_line_preview
from app.retrieval.vectorstore import get_vector_store

logger = logging.getLogger(__name__)

_QUERY_PREVIEW_WIDTH = 120
_SUPPORTED_SEARCH_TYPES = {"similarity", "mmr"}


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    content: str
    document_id: str | None
    source: str
    page: str | None
    chunk_index: int | None
    metadata: dict[str, Any]

    @classmethod
    def from_document(cls, doc: Document, rank: int) -> "RetrievedChunk":
        metadata = dict(doc.metadata or {})
        return cls(
            rank=rank,
            content=doc.page_content,
            document_id=getattr(doc, "id", None),
            source=metadata.get("source", "unknown"),
            page=normalize_page(metadata.get("page")),
            chunk_index=normalize_chunk_index(metadata.get("chunk_index")),
            metadata=metadata,
        )


def _normalize_search_type(search_type: str | None) -> str:
    normalized = (search_type or settings.retrieval_search_type).lower()
    if normalized not in _SUPPORTED_SEARCH_TYPES:
        raise ValueError(f"Unsupported retrieval search type: {normalized}")
    return normalized


def _search_documents(
    query: str,
    *,
    top_k: int,
    search_type: str,
    fetch_k: int,
) -> list[Document]:
    vector_store = get_vector_store()
    # 多样性搜索 尽量找内容不重复的资料
    if search_type == "mmr":
        return vector_store.max_marginal_relevance_search(
            query,
            k=top_k,
            fetch_k=fetch_k,
        )
    return vector_store.similarity_search(query, k=top_k)


def retrieve_chunks(
    query: str,
    *,
    top_k: int | None = None,
    search_type: str | None = None,
    fetch_k: int | None = None,
) -> list[RetrievedChunk]:
    resolved_top_k = top_k or settings.top_k
    resolved_search_type = _normalize_search_type(search_type)
    resolved_fetch_k = max(fetch_k or settings.retrieval_fetch_k, resolved_top_k)

    logger.info(
        "执行检索。search_type=%s top_k=%s fetch_k=%s query_preview=%s",
        resolved_search_type,
        resolved_top_k,
        resolved_fetch_k,
        single_line_preview(query, width=_QUERY_PREVIEW_WIDTH),
    )

    docs = _search_documents(
        query,
        top_k=resolved_top_k,
        search_type=resolved_search_type,
        fetch_k=resolved_fetch_k,
    )

    chunks = [RetrievedChunk.from_document(doc, rank=index) for index, doc in enumerate(docs, start=1)]
    logger.info("检索完成。search_type=%s hit_count=%s", resolved_search_type, len(chunks))
    return chunks
