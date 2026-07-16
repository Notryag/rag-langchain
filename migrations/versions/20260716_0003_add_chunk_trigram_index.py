"""add document chunk trigram index

Revision ID: 20260716_0003
Revises: 20260715_0002
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260716_0003"
down_revision: Union[str, None] = "20260715_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_document_chunks_content_trgm",
        "document_chunks",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_trgm", table_name="document_chunks", postgresql_using="gin")
