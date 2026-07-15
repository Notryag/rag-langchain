from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class PromptVersion(TimestampMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("uq_prompt_versions_name_version", "name", "version", unique=True),
        Index(
            "uq_prompt_versions_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
