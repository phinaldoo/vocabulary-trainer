"""promote the first existing user when no administrator exists

Revision ID: 7b4f3e9d2a10
Revises: c43ca1f2a9e7
Create Date: 2026-09-02 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b4f3e9d2a10"
down_revision: str | Sequence[str] | None = "c43ca1f2a9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'admin'
            WHERE id = (
                SELECT id
                FROM users
                ORDER BY created_at, id
                LIMIT 1
            )
            AND NOT EXISTS (
                SELECT 1
                FROM users
                WHERE role = 'admin'
            )
            """
        )
    )


def downgrade() -> None:
    # Role changes may have been made after this migration. A downgrade must not
    # guess which administrator, if any, should be demoted.
    pass
