from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    thread_id: str | None = Field(default=None, max_length=128)


class ThreadResponse(BaseModel):
    thread_id: str


class HealthResponse(BaseModel):
    status: str


class PublicConfigResponse(BaseModel):
    chat_model: str
    embedding_model: str
    top_k: int
    retrieval_search_type: str
    retrieval_fetch_k: int
    reranker_enabled: bool
    reranker_strategy: str
    retrieval_max_context_chars: int
    collection_name: str


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    status_lines: list[str]
    citations: list[dict[str, Any]]
    usage: dict[str, Any] | None
    elapsed_ms: int | None
