from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.retrieval.profile import RetrievalProfile


class RetrievalProfileRequest(BaseModel):
    search_type: str | None = Field(default=None)
    top_k: int | None = Field(default=None, gt=0)
    fetch_k: int | None = Field(default=None, gt=0)
    reranker_enabled: bool | None = None
    max_context_chars: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_profile(self) -> "RetrievalProfileRequest":
        self.to_profile()
        return self

    def to_profile(self) -> RetrievalProfile:
        return RetrievalProfile.from_settings().with_overrides(
            search_type=self.search_type,
            top_k=self.top_k,
            fetch_k=self.fetch_k,
            reranker_enabled=self.reranker_enabled,
            max_context_chars=self.max_context_chars,
        )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    thread_id: str | None = Field(default=None, max_length=128)
    retrieval_profile: RetrievalProfileRequest | None = None


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


class ChatStreamAnswerData(BaseModel):
    content: str
    answer: str


class ChatStreamToolData(BaseModel):
    status_line: str | None
    tool_name: str | None
    content: str
    citations: list[dict[str, Any]]


class ChatStreamErrorData(BaseModel):
    message: str
