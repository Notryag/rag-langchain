from __future__ import annotations

import re
from typing import Any

from typing_extensions import NotRequired, TypedDict

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
    label: NotRequired[str]


def _normalize_page(page: Any) -> str | None:
    if page in ("", None, "na"):
        return None
    return str(page)


def _normalize_chunk_index(chunk_index: Any) -> int | None:
    if chunk_index in (None, ""):
        return None
    return int(chunk_index)


def build_citation_label(*, source: str, page: str | None, chunk_index: int | None) -> str:
    parts = [f"source={source}"]
    if page not in (None, "", "na"):
        parts.append(f"page={page}")
    if chunk_index not in (None, ""):
        parts.append(f"chunk={chunk_index}")
    return ", ".join(parts)


def citation_key(citation: Citation) -> tuple[Any, ...]:
    return (
        citation.get("rank"),
        citation.get("source"),
        citation.get("page"),
        citation.get("chunk_index"),
    )


def with_citation_label(citation: Citation) -> Citation:
    labeled = dict(citation)
    labeled["label"] = build_citation_label(
        source=citation["source"],
        page=citation.get("page"),
        chunk_index=citation.get("chunk_index"),
    )
    return labeled


def _match_to_citation(match: re.Match[str]) -> Citation:
    citation: Citation = {
        "rank": int(match.group("rank")),
        "source": match.group("source"),
        "page": _normalize_page(match.group("page")),
        "chunk_index": _normalize_chunk_index(match.group("chunk")),
    }
    return with_citation_label(citation)


def extract_citations_from_text(text: str) -> list[Citation]:
    return [_match_to_citation(match) for match in _CITATION_LINE_RE.finditer(text)]
