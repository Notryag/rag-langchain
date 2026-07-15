from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
        nullable=False,
        index=True,
    )

    knowledge_bases = relationship("KnowledgeBase", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
