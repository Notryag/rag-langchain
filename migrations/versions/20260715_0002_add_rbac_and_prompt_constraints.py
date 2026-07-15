"""add RBAC and prompt constraints

Revision ID: 20260715_0002
Revises: 20260617_0001
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0002"
down_revision: Union[str, None] = "20260617_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = postgresql.ENUM("user", "admin", name="user_role", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("role", user_role, server_default="user", nullable=False),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index(
        "uq_prompt_versions_name_version",
        "prompt_versions",
        ["name", "version"],
        unique=True,
    )
    op.create_index(
        "uq_prompt_versions_single_active",
        "prompt_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_prompt_versions_single_active", table_name="prompt_versions")
    op.drop_index("uq_prompt_versions_name_version", table_name="prompt_versions")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
