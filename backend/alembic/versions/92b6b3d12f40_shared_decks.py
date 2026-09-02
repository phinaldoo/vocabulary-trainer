"""shared decks and administrator-managed generic cards

Revision ID: 92b6b3d12f40
Revises: 6e43d539df86
Create Date: 2026-08-31 14:00:00.000000
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "92b6b3d12f40"
down_revision: str | None = "6e43d539df86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECK_ID = uuid.UUID("7932ce10-9eb3-5ab9-8bb9-9c5e7a21178b")


def section_id(number: int) -> uuid.UUID:
    return uuid.uuid5(DECK_ID, f"section:lesson-{number}")


def upgrade() -> None:
    now = datetime.now(UTC)
    connection = op.get_bind()
    legacy_card_count = int(connection.scalar(sa.text("SELECT count(*) FROM vocabulary")) or 0)
    op.create_table(
        "decks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("front_label", sa.String(length=80), nullable=False),
        sa.Column("back_label", sa.String(length=80), nullable=False),
        sa.Column("front_language", sa.String(length=35), nullable=False),
        sa.Column("back_language", sa.String(length=35), nullable=False),
        sa.Column("front_matcher", sa.String(length=32), nullable=False),
        sa.Column("back_matcher", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("license", sa.String(length=80), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="decks_status_check"
        ),
        sa.CheckConstraint("version >= 1", name="decks_version_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("sort_order", name="uq_decks_sort_order"),
    )
    op.create_index(op.f("ix_decks_slug"), "decks", ["slug"], unique=True)
    op.create_index(op.f("ix_decks_status"), "decks", ["status"], unique=False)
    decks = sa.table(
        "decks",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("title", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("front_label", sa.String()),
        sa.column("back_label", sa.String()),
        sa.column("front_language", sa.String()),
        sa.column("back_language", sa.String()),
        sa.column("front_matcher", sa.String()),
        sa.column("back_matcher", sa.String()),
        sa.column("status", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("license", sa.String()),
        sa.column("attribution", sa.Text()),
        sa.column("content_hash", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    if legacy_card_count:
        op.bulk_insert(
            decks,
            [
                {
                    "id": DECK_ID,
                    "slug": "latin-german",
                    "title": "Latein – Deutsch",
                    "description": "Migrierter gemeinsamer lateinisch-deutscher Wortschatz",
                    "front_label": "Latein",
                    "back_label": "Deutsch",
                    "front_language": "la",
                    "back_language": "de",
                    "front_matcher": "latin-v1",
                    "back_matcher": "german-v1",
                    "status": "published",
                    "version": 1,
                    "license": None,
                    "attribution": None,
                    "content_hash": None,
                    "sort_order": 1,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )

    op.create_table(
        "sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deck_id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deck_id", "sort_order", name="uq_sections_deck_order"),
        sa.UniqueConstraint("deck_id", "stable_key", name="uq_sections_deck_key"),
    )
    op.create_index(op.f("ix_sections_deck_id"), "sections", ["deck_id"], unique=False)
    op.create_index(
        "idx_sections_deck_active_order",
        "sections",
        ["deck_id", "active", "sort_order"],
        unique=False,
    )
    sections = sa.table(
        "sections",
        sa.column("id", sa.Uuid()),
        sa.column("deck_id", sa.Uuid()),
        sa.column("stable_key", sa.String()),
        sa.column("title", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    if legacy_card_count:
        op.bulk_insert(
            sections,
            [
                {
                    "id": section_id(number),
                    "deck_id": DECK_ID,
                    "stable_key": f"lesson-{number}",
                    "title": f"Lektion {number}",
                    "sort_order": number,
                    "active": True,
                }
                for number in range(1, 98)
            ],
        )

    op.drop_constraint("users_direction_check", "users", type_="check")
    op.drop_constraint("users_input_mode_check", "users", type_="check")
    op.drop_constraint("users_selected_chapter_check", "users", type_="check")
    op.add_column(
        "users", sa.Column("role", sa.String(length=16), server_default="user", nullable=False)
    )
    op.add_column("users", sa.Column("selected_deck_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("selected_section_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE users SET direction = 'forward' WHERE direction = 'latin-deutsch'")
    op.execute("UPDATE users SET direction = 'reverse' WHERE direction = 'deutsch-latein'")
    op.execute("UPDATE users SET direction = 'mixed' WHERE direction = 'gemischt'")
    op.execute("UPDATE users SET input_mode = 'typing' WHERE input_mode = 'tippen'")
    op.execute("UPDATE users SET input_mode = 'reveal' WHERE input_mode = 'aufdecken'")
    users = sa.table(
        "users",
        sa.column("selected_chapter", sa.Integer()),
        sa.column("selected_deck_id", sa.Uuid()),
        sa.column("selected_section_id", sa.Uuid()),
    )
    if legacy_card_count:
        op.execute(users.update().values(selected_deck_id=DECK_ID))
        for number in range(1, 98):
            op.execute(
                users.update()
                .where(users.c.selected_chapter == number)
                .values(selected_section_id=section_id(number))
            )
    op.create_foreign_key(
        "fk_users_selected_deck",
        "users",
        "decks",
        ["selected_deck_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_selected_section",
        "users",
        "sections",
        ["selected_section_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("users", "selected_chapter")
    op.alter_column("users", "direction", existing_type=sa.String(length=24), type_=sa.String(16))
    op.create_check_constraint(
        "users_direction_check", "users", "direction IN ('forward', 'reverse', 'mixed')"
    )
    op.create_check_constraint(
        "users_input_mode_check", "users", "input_mode IN ('typing', 'reveal')"
    )
    op.create_check_constraint("users_role_check", "users", "role IN ('user', 'admin')")

    op.rename_table("vocabulary", "cards")
    op.drop_index("idx_vocabulary_lesson_id", table_name="cards")
    op.drop_index("ix_vocabulary_lesson", table_name="cards")
    op.drop_constraint("vocabulary_lesson_check", "cards", type_="check")
    op.drop_constraint("vocabulary_sort_order_key", "cards", type_="unique")
    op.drop_constraint("vocabulary_stable_key_key", "cards", type_="unique")
    op.alter_column("cards", "stable_key", existing_type=sa.String(length=80), type_=sa.String(160))
    op.alter_column("cards", "latin", new_column_name="front_text")
    op.alter_column("cards", "german", new_column_name="back_text")
    op.add_column("cards", sa.Column("deck_id", sa.Uuid(), nullable=True))
    op.add_column("cards", sa.Column("section_id", sa.Uuid(), nullable=True))
    op.add_column(
        "cards",
        sa.Column("front_answers", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column(
        "cards",
        sa.Column("back_answers", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column(
        "cards", sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
    )
    cards = sa.table(
        "cards",
        sa.column("id", sa.Uuid()),
        sa.column("deck_id", sa.Uuid()),
        sa.column("section_id", sa.Uuid()),
        sa.column("lesson", sa.Integer()),
        sa.column("feature", sa.Text()),
        sa.column("part_of_speech", sa.Text()),
        sa.column("grammar", sa.Text()),
        sa.column("info", sa.Text()),
        sa.column("note", sa.Text()),
        sa.column("metadata", sa.JSON()),
    )
    if legacy_card_count:
        op.execute(cards.update().values(deck_id=DECK_ID))
        for number in range(1, 98):
            op.execute(
                cards.update().where(cards.c.lesson == number).values(section_id=section_id(number))
            )
    legacy_rows = connection.execute(
        sa.select(
            cards.c.id,
            cards.c.feature,
            cards.c.part_of_speech,
            cards.c.grammar,
            cards.c.info,
            cards.c.note,
        )
    ).all()
    for row in legacy_rows:
        values = {
            key: value
            for key, value in {
                "feature": row.feature,
                "partOfSpeech": row.part_of_speech,
                "grammar": row.grammar,
                "info": row.info,
                "note": row.note,
            }.items()
            if value is not None
        }
        connection.execute(cards.update().where(cards.c.id == row.id).values(metadata=values))
    op.alter_column("cards", "deck_id", nullable=False)
    op.create_foreign_key(
        "fk_cards_deck", "cards", "decks", ["deck_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_cards_section", "cards", "sections", ["section_id"], ["id"], ondelete="SET NULL"
    )
    op.create_unique_constraint("uq_cards_deck_key", "cards", ["deck_id", "stable_key"])
    op.create_unique_constraint("uq_cards_deck_order", "cards", ["deck_id", "sort_order"])
    op.create_index(op.f("ix_cards_deck_id"), "cards", ["deck_id"], unique=False)
    op.create_index(op.f("ix_cards_section_id"), "cards", ["section_id"], unique=False)
    op.create_index(
        "idx_cards_deck_section_order",
        "cards",
        ["deck_id", "section_id", "sort_order"],
        unique=False,
    )
    op.create_index("idx_cards_deck_active", "cards", ["deck_id", "active"], unique=False)
    for name in (
        "lesson",
        "source_record",
        "source_id",
        "feature",
        "part_of_speech",
        "grammar",
        "info",
        "note",
    ):
        op.drop_column("cards", name)

    op.rename_table("user_vocabulary_progress", "user_card_progress")
    op.drop_index("ix_user_vocabulary_progress_due_at", table_name="user_card_progress")
    op.create_index(
        op.f("ix_user_card_progress_due_at"),
        "user_card_progress",
        ["due_at"],
        unique=False,
    )
    op.drop_constraint("progress_direction_check", "user_card_progress", type_="check")
    op.alter_column("user_card_progress", "vocabulary_id", new_column_name="card_id")
    op.execute(
        "UPDATE user_card_progress SET direction = 'forward' WHERE direction = 'latin-deutsch'"
    )
    op.execute(
        "UPDATE user_card_progress SET direction = 'reverse' WHERE direction = 'deutsch-latein'"
    )
    op.alter_column(
        "user_card_progress", "direction", existing_type=sa.String(length=24), type_=sa.String(16)
    )
    op.create_check_constraint(
        "progress_direction_check",
        "user_card_progress",
        "direction IN ('forward', 'reverse')",
    )

    op.alter_column("user_favorites", "vocabulary_id", new_column_name="card_id")

    op.drop_constraint("reviews_direction_check", "review_events", type_="check")
    op.drop_constraint("uq_reviews_state_version", "review_events", type_="unique")
    op.alter_column("review_events", "vocabulary_id", new_column_name="card_id")
    op.execute("UPDATE review_events SET direction = 'forward' WHERE direction = 'latin-deutsch'")
    op.execute("UPDATE review_events SET direction = 'reverse' WHERE direction = 'deutsch-latein'")
    op.alter_column(
        "review_events", "direction", existing_type=sa.String(length=24), type_=sa.String(16)
    )
    op.create_check_constraint(
        "reviews_direction_check", "review_events", "direction IN ('forward', 'reverse')"
    )
    op.create_unique_constraint(
        "uq_reviews_state_version",
        "review_events",
        ["user_id", "card_id", "direction", "base_version"],
    )

    op.drop_constraint("study_sessions_direction_check", "study_sessions", type_="check")
    op.drop_constraint("study_sessions_input_mode_check", "study_sessions", type_="check")
    op.drop_constraint("study_sessions_chapter_check", "study_sessions", type_="check")
    op.add_column("study_sessions", sa.Column("deck_id", sa.Uuid(), nullable=True))
    op.add_column("study_sessions", sa.Column("section_id", sa.Uuid(), nullable=True))
    study_sessions = sa.table(
        "study_sessions",
        sa.column("chapter", sa.Integer()),
        sa.column("deck_id", sa.Uuid()),
        sa.column("section_id", sa.Uuid()),
    )
    if legacy_card_count:
        op.execute(study_sessions.update().values(deck_id=DECK_ID))
        for number in range(1, 98):
            op.execute(
                study_sessions.update()
                .where(study_sessions.c.chapter == number)
                .values(section_id=section_id(number))
            )
    op.execute("UPDATE study_sessions SET direction = 'forward' WHERE direction = 'latin-deutsch'")
    op.execute("UPDATE study_sessions SET direction = 'reverse' WHERE direction = 'deutsch-latein'")
    op.execute("UPDATE study_sessions SET direction = 'mixed' WHERE direction = 'gemischt'")
    op.execute("UPDATE study_sessions SET input_mode = 'typing' WHERE input_mode = 'tippen'")
    op.execute("UPDATE study_sessions SET input_mode = 'reveal' WHERE input_mode = 'aufdecken'")
    op.alter_column("study_sessions", "deck_id", nullable=False)
    op.alter_column(
        "study_sessions", "direction", existing_type=sa.String(length=24), type_=sa.String(16)
    )
    op.create_foreign_key(
        "fk_study_sessions_deck",
        "study_sessions",
        "decks",
        ["deck_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_study_sessions_section",
        "study_sessions",
        "sections",
        ["section_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("study_sessions", "chapter")
    op.create_check_constraint(
        "study_sessions_direction_check",
        "study_sessions",
        "direction IN ('forward', 'reverse', 'mixed')",
    )
    op.create_check_constraint(
        "study_sessions_input_mode_check",
        "study_sessions",
        "input_mode IN ('typing', 'reveal')",
    )

    op.drop_constraint("study_items_direction_check", "study_session_items", type_="check")
    op.drop_constraint("uq_study_session_card", "study_session_items", type_="unique")
    op.drop_constraint(
        "study_session_items_vocabulary_id_fkey",
        "study_session_items",
        type_="foreignkey",
    )
    op.alter_column("study_session_items", "vocabulary_id", new_column_name="card_id")
    op.add_column("study_session_items", sa.Column("prompt_snapshot", sa.Text(), nullable=True))
    op.add_column("study_session_items", sa.Column("solution_snapshot", sa.Text(), nullable=True))
    op.add_column(
        "study_session_items",
        sa.Column(
            "accepted_answers_snapshot", sa.JSON(), server_default=sa.text("'[]'"), nullable=True
        ),
    )
    op.add_column(
        "study_session_items",
        sa.Column("metadata_snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
    )
    op.add_column(
        "study_session_items", sa.Column("prompt_language", sa.String(length=35), nullable=True)
    )
    op.add_column(
        "study_session_items", sa.Column("answer_language", sa.String(length=35), nullable=True)
    )
    op.add_column(
        "study_session_items", sa.Column("matcher_profile", sa.String(length=32), nullable=True)
    )
    op.execute(
        "UPDATE study_session_items SET direction = 'forward' WHERE direction = 'latin-deutsch'"
    )
    op.execute(
        "UPDATE study_session_items SET direction = 'reverse' WHERE direction = 'deutsch-latein'"
    )
    op.execute(
        sa.text(
            """
            UPDATE study_session_items AS item
            SET prompt_snapshot = CASE
                    WHEN item.direction = 'forward' THEN card.front_text
                    ELSE card.back_text
                END,
                solution_snapshot = CASE
                    WHEN item.direction = 'forward' THEN card.back_text
                    ELSE card.front_text
                END,
                accepted_answers_snapshot = CASE
                    WHEN item.direction = 'forward' THEN card.back_answers
                    ELSE card.front_answers
                END,
                metadata_snapshot = card.metadata,
                prompt_language = CASE
                    WHEN item.direction = 'forward' THEN deck.front_language
                    ELSE deck.back_language
                END,
                answer_language = CASE
                    WHEN item.direction = 'forward' THEN deck.back_language
                    ELSE deck.front_language
                END,
                matcher_profile = CASE
                    WHEN item.direction = 'forward' THEN deck.back_matcher
                    ELSE deck.front_matcher
                END
            FROM cards AS card
            JOIN decks AS deck ON deck.id = card.deck_id
            WHERE item.card_id = card.id
            """
        )
    )
    for name in (
        "prompt_snapshot",
        "solution_snapshot",
        "accepted_answers_snapshot",
        "metadata_snapshot",
        "prompt_language",
        "answer_language",
        "matcher_profile",
    ):
        op.alter_column("study_session_items", name, nullable=False)
    op.alter_column(
        "study_session_items", "direction", existing_type=sa.String(length=24), type_=sa.String(16)
    )
    op.create_check_constraint(
        "study_items_direction_check",
        "study_session_items",
        "direction IN ('forward', 'reverse')",
    )
    op.create_unique_constraint(
        "uq_study_session_card",
        "study_session_items",
        ["session_id", "card_id", "direction"],
    )
    op.create_foreign_key(
        "fk_study_session_items_card",
        "study_session_items",
        "cards",
        ["card_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_table("dataset_versions")
    op.create_table(
        "deck_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deck_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deck_id", "sha256", name="uq_deck_versions_hash"),
        sa.UniqueConstraint("deck_id", "version", name="uq_deck_versions_version"),
    )
    op.create_index(op.f("ix_deck_versions_deck_id"), "deck_versions", ["deck_id"], unique=False)
    op.drop_table("chapters")


def downgrade() -> None:
    raise RuntimeError(
        "This data-preserving domain migration cannot be downgraded automatically. "
        "Restore a pre-migration backup instead."
    )
