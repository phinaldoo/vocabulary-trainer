"""Allow daily goals up to 500 cards."""

from alembic import op

revision = "e8a12f4b6c90"
down_revision = "c43ca1f2a9e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("users_daily_goal_check", "users", type_="check")
    op.create_check_constraint(
        "users_daily_goal_check", "users", "daily_goal BETWEEN 5 AND 500"
    )


def downgrade() -> None:
    op.execute("UPDATE users SET daily_goal = 50 WHERE daily_goal > 50")
    op.drop_constraint("users_daily_goal_check", "users", type_="check")
    op.create_check_constraint(
        "users_daily_goal_check", "users", "daily_goal BETWEEN 5 AND 50"
    )
