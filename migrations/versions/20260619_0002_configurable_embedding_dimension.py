"""configurable embedding dimension

Revision ID: 20260619_0002
Revises: 20260617_0001
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op

from app.config.settings import settings

revision: str = "20260619_0002"
down_revision: Union[str, None] = "20260617_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({settings.embedding_dimension})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536)")
