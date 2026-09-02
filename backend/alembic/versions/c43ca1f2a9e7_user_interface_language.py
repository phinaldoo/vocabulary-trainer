"""add per-user interface language

Revision ID: c43ca1f2a9e7
Revises: 92b6b3d12f40
Create Date: 2026-08-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c43ca1f2a9e7"
down_revision: str | Sequence[str] | None = "92b6b3d12f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "users_language_check",
        "users",
        "language IS NULL OR language IN ('en', 'zh-Hans', 'hi', 'es', 'de')",
    )


def downgrade() -> None:
    op.drop_constraint("users_language_check", "users", type_="check")
    op.drop_column("users", "language")
