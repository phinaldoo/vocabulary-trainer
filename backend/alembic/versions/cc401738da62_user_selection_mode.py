"""Remember the learner's card selection mode across visits."""

import sqlalchemy as sa

from alembic import op

revision = "cc401738da62"
down_revision = "ab3e1492c501"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("selection_mode", sa.String(16), nullable=False, server_default="scheduled"),
    )
    with op.batch_alter_table("users") as batch:
        batch.create_check_constraint(
            "users_selection_mode_check", "selection_mode IN ('scheduled', 'random', 'adaptive')"
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_selection_mode_check", type_="check")
        batch.drop_column("selection_mode")
