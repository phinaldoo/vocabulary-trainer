"""Restore ordinary vocabulary defaults overwritten by special-verb sessions."""

from alembic import op

revision = "a51b6c7d8e90"
down_revision = "d013eba49876"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Correlated subqueries work on both PostgreSQL and SQLite. Restore the most
    # recent published vocabulary session, including its multiple-section choice.
    # With no such history, select the first ordinary deck and all its sections.
    latest = """
        FROM study_sessions AS s JOIN decks AS d ON d.id = s.deck_id
        WHERE s.user_id = users.id AND d.status = 'published'
          AND d.front_matcher != 'latin-principal-parts-v1'
        ORDER BY s.started_at DESC, s.id DESC LIMIT 1
    """
    op.execute(f"""
        UPDATE users SET
          selected_deck_id = COALESCE((SELECT s.deck_id {latest}), (
            SELECT id FROM decks WHERE status = 'published'
              AND front_matcher != 'latin-principal-parts-v1'
            ORDER BY sort_order LIMIT 1
          )),
          selected_section_id = (SELECT s.section_id {latest}),
          selected_section_ids = (SELECT s.section_ids {latest}),
          direction = COALESCE((SELECT s.direction {latest}), 'forward'),
          input_mode = COALESCE((SELECT s.input_mode {latest}), 'typing'),
          selection_mode = COALESCE((SELECT s.selection_mode {latest}), 'scheduled')
        WHERE selected_deck_id IN (
          SELECT id FROM decks WHERE front_matcher = 'latin-principal-parts-v1'
        )
    """)


def downgrade() -> None:
    # Restored preferences are user data; do not reintroduce the overwritten values.
    pass
