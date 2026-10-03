"""Add dedicated mistake practice to persisted selection modes."""

from alembic import op

revision = "d013eba49876"
down_revision = "cc401738da62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_selection_mode_check", type_="check")
        batch.create_check_constraint(
            "users_selection_mode_check",
            "selection_mode IN ('scheduled', 'random', 'adaptive', 'mistakes')",
        )
    with op.batch_alter_table("study_sessions") as batch:
        batch.create_check_constraint(
            "study_sessions_selection_mode_check",
            "selection_mode IN ('scheduled', 'random', 'adaptive', 'mistakes')",
        )


def downgrade() -> None:
    op.execute("UPDATE users SET selection_mode = 'scheduled' WHERE selection_mode = 'mistakes'")
    op.execute(
        "UPDATE study_sessions SET selection_mode = 'scheduled' WHERE selection_mode = 'mistakes'"
    )
    with op.batch_alter_table("study_sessions") as batch:
        batch.drop_constraint("study_sessions_selection_mode_check", type_="check")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_selection_mode_check", type_="check")
        batch.create_check_constraint(
            "users_selection_mode_check",
            "selection_mode IN ('scheduled', 'random', 'adaptive')",
        )
