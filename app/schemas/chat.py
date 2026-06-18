from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.chat import ChatRole


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    session_id: int | None = None


class ChatAnswerResponse(BaseModel):
    answer: str
    references: list[dict[str, Any]]
    session_id: int


class ChatSessionRead(BaseModel):
    id: int
    user_id: int
    kb_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: ChatRole
    content: str
    references: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
