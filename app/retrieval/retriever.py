from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from textwrap import shorten
from typing import Any, Mapping, TypedDict

from langchain_core.documents import Document

from app.config.settings import settings
from app.retrieval.vectorstore import get_vector_store

logger = logging.getLogger(__name__)

_QUERY_PREVIEW_WIDTH = 120
_CHUNK_PREVIEW_WIDTH = 1200
_SUPPORTED_SEARCH_TYPES = {"similarity", "mmr"}

_CITATION_LINE_RE = re.compile(
    r"^\[(?P<rank>\d+)\] source=(?P<source>[^,\n]+)"
    r"(?:, page=(?P<page>[^,\n]+))?"
    r"(?:, chunk=(?P<chunk>[^,\n]+))?$",
    re.MULTILINE,
)


class Citation(TypedDict):
    rank: int
    source: str
    page: str | None
    chunk_index: int | None


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
            page=_normalize_page(metadata.get("page")),
            chunk_index=_normalize_chunk_index(metadata.get("chunk_index")),
            metadata=metadata,
        )

    def format_citation_label(self) -> str:
        return _compose_citation_label(
            source=self.source,
            page=self.page,
            chunk_index=self.chunk_index,
        )

    def format_for_context(self) -> str:
        content = _single_line_preview(self.content, width=_CHUNK_PREVIEW_WIDTH)
        return f"[{self.rank}] {self.format_citation_label()}\n{content}"


def _normalize_page(page: Any) -> str | None:
    if page in ("", None, "na"):
        return None
    return str(page)


def _normalize_chunk_index(chunk_index: Any) -> int | None:
    if chunk_index in (None, ""):
        return None
    return int(chunk_index)


def _single_line_preview(text: str, *, width: int) -> str:
    return shorten(text.replace("\n", " "), width=width, placeholder="...")


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
        _single_line_preview(query, width=_QUERY_PREVIEW_WIDTH),
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


def _compose_citation_label(*, source: str, page: str | None, chunk_index: int | None) -> str:
    parts = [f"source={source}"]
    if page not in (None, "", "na"):
        parts.append(f"page={page}")
    if chunk_index not in (None, ""):
        parts.append(f"chunk={chunk_index}")
    return ", ".join(parts)


def _citation_parts(citation: Mapping[str, Any] | RetrievedChunk) -> tuple[str, str | None, int | None]:
    if isinstance(citation, RetrievedChunk):
        return citation.source, citation.page, citation.chunk_index
    return (
        str(citation.get("source", "unknown")),
        _normalize_page(citation.get("page")),
        _normalize_chunk_index(citation.get("chunk_index")),
    )


def format_citation_label(citation: Citation | RetrievedChunk) -> str:
    source, page, chunk_index = _citation_parts(citation)
    return _compose_citation_label(
        source=source,
        page=page,
        chunk_index=chunk_index,
    )


def format_retrieved_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant context found."

    return "\n\n".join(chunk.format_for_context() for chunk in chunks)


def _match_to_citation(match: re.Match[str]) -> Citation:
    return {
        "rank": int(match.group("rank")),
        "source": match.group("source"),
        "page": _normalize_page(match.group("page")),
        "chunk_index": _normalize_chunk_index(match.group("chunk")),
    }


def extract_citations_from_text(text: str) -> list[Citation]:
    return [_match_to_citation(match) for match in _CITATION_LINE_RE.finditer(text)]
