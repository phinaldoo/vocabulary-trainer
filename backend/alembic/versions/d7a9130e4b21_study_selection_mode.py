"""Persist study session selection mode.

Revision ID: d7a9130e4b21
Revises: f19d3a7b2c60
"""

import sqlalchemy as sa

from alembic import op

revision = "d7a9130e4b21"
down_revision = "f19d3a7b2c60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "study_sessions",
        sa.Column("selection_mode", sa.String(16), server_default="scheduled", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("study_sessions", "selection_mode")
