"""Personal vocabulary difficulty, independent of review history."""

import sqlalchemy as sa

from alembic import op

revision = "ab3e1492c501"
down_revision = "b82a4c9d1e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_card_preferences",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'normal', 'hard')", name="preference_difficulty_check"
        ),
    )


def downgrade() -> None:
    op.drop_table("user_card_preferences")
