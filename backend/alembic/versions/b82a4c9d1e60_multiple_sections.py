"""Persist multiple selected sections, retaining legacy single-section selections."""

import sqlalchemy as sa

from alembic import op

revision = "b82a4c9d1e60"
down_revision = "d7a9130e4b21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("selected_section_ids", sa.JSON(), nullable=True))
    op.add_column("study_sessions", sa.Column("section_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("study_sessions", "section_ids")
    op.drop_column("users", "selected_section_ids")
