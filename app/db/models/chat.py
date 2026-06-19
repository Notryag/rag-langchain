from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kb_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("User", back_populates="chat_sessions")
    knowledge_base = relationship("KnowledgeBase", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    runs = relationship("ChatRun", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[ChatRole] = mapped_column(
        Enum(ChatRole, name="chat_role", values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    session = relationship("ChatSession", back_populates="messages")


class ChatRun(TimestampMixin, Base):
    __tablename__ = "chat_runs"
    __table_args__ = (
        Index("ix_chat_runs_user_kb_status", "user_id", "kb_id", "status"),
        Index("ix_chat_runs_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kb_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[ChatRunStatus] = mapped_column(
        Enum(ChatRunStatus, name="chat_run_status", values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        default=ChatRunStatus.RUNNING,
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("ChatSession", back_populates="runs")
