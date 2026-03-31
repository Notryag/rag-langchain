from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from textwrap import shorten
from typing import Any

from langchain_core.documents import Document

from app.config.settings import settings
from app.retrieval.vectorstore import get_vector_store

logger = logging.getLogger(__name__)

_CITATION_LINE_RE = re.compile(
    r"^\[(?P<rank>\d+)\] source=(?P<source>[^,\n]+)"
    r"(?:, page=(?P<page>[^,\n]+))?"
    r"(?:, chunk=(?P<chunk>[^,\n]+))?$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    content: str
    document_id: str | None
    source: str
    page: str | None
    chunk_index: int | None
    metadata: dict[str, Any]


def _normalize_page(page: Any) -> str | None:
    if page in ("", None, "na"):
        return None
    return str(page)


def _normalize_search_type(search_type: str | None) -> str:
    normalized = (search_type or settings.retrieval_search_type).lower()
    if normalized not in {"similarity", "mmr"}:
        raise ValueError(f"Unsupported retrieval search type: {normalized}")
    return normalized


def _doc_to_chunk(doc: Document, rank: int) -> RetrievedChunk:
    metadata = dict(doc.metadata or {})
    chunk_index = metadata.get("chunk_index")
    return RetrievedChunk(
        rank=rank,
        content=doc.page_content,
        document_id=getattr(doc, "id", None),
        source=metadata.get("source", "unknown"),
        page=_normalize_page(metadata.get("page")),
        chunk_index=int(chunk_index) if chunk_index not in (None, "") else None,
        metadata=metadata,
    )


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
        shorten(query.replace("\n", " "), width=120, placeholder="..."),
    )

    vector_store = get_vector_store()
    if resolved_search_type == "mmr":
        docs = vector_store.max_marginal_relevance_search(
            query,
            k=resolved_top_k,
            fetch_k=resolved_fetch_k,
        )
    else:
        docs = vector_store.similarity_search(query, k=resolved_top_k)

    chunks = [_doc_to_chunk(doc, rank=index) for index, doc in enumerate(docs, start=1)]
    logger.info("检索完成。search_type=%s hit_count=%s", resolved_search_type, len(chunks))
    return chunks


def format_citation_label(citation: dict[str, Any] | RetrievedChunk) -> str:
    source = citation.source if isinstance(citation, RetrievedChunk) else citation.get("source", "unknown")
    page = citation.page if isinstance(citation, RetrievedChunk) else citation.get("page")
    chunk_index = citation.chunk_index if isinstance(citation, RetrievedChunk) else citation.get("chunk_index")

    parts = [f"source={source}"]
    if page not in (None, "", "na"):
        parts.append(f"page={page}")
    if chunk_index not in (None, ""):
        parts.append(f"chunk={chunk_index}")
    return ", ".join(parts)


def format_retrieved_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant context found."

    blocks = []
    for chunk in chunks:
        content = shorten(chunk.content.replace("\n", " "), width=1200, placeholder="...")
        blocks.append(f"[{chunk.rank}] {format_citation_label(chunk)}\n{content}")
    return "\n\n".join(blocks)


def extract_citations_from_text(text: str) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for match in _CITATION_LINE_RE.finditer(text):
        chunk_value = match.group("chunk")
        citations.append(
            {
                "rank": int(match.group("rank")),
                "source": match.group("source"),
                "page": match.group("page"),
                "chunk_index": int(chunk_value) if chunk_value not in (None, "") else None,
            }
        )
    return citations
