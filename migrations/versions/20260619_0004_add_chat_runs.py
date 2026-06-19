"""add chat runs

Revision ID: 20260619_0004
Revises: 20260619_0003
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260619_0004"
down_revision: Union[str, None] = "20260619_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    chat_run_status = postgresql.ENUM(
        "running",
        "completed",
        "failed",
        "cancelled",
        name="chat_run_status",
        create_type=False,
    )
    chat_run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chat_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("status", chat_run_status, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_runs_session_id", "chat_runs", ["session_id"])
    op.create_index("ix_chat_runs_user_id", "chat_runs", ["user_id"])
    op.create_index("ix_chat_runs_kb_id", "chat_runs", ["kb_id"])
    op.create_index("ix_chat_runs_status", "chat_runs", ["status"])
    op.create_index("ix_chat_runs_user_kb_status", "chat_runs", ["user_id", "kb_id", "status"])
    op.create_index("ix_chat_runs_session_created", "chat_runs", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_runs_session_created", table_name="chat_runs")
    op.drop_index("ix_chat_runs_user_kb_status", table_name="chat_runs")
    op.drop_index("ix_chat_runs_status", table_name="chat_runs")
    op.drop_index("ix_chat_runs_kb_id", table_name="chat_runs")
    op.drop_index("ix_chat_runs_user_id", table_name="chat_runs")
    op.drop_index("ix_chat_runs_session_id", table_name="chat_runs")
    op.drop_table("chat_runs")
    sa.Enum(name="chat_run_status").drop(op.get_bind(), checkfirst=True)
