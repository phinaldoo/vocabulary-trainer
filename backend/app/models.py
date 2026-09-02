from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("daily_goal BETWEEN 5 AND 50", name="users_daily_goal_check"),
        CheckConstraint(
            "direction IN ('forward', 'reverse', 'mixed')",
            name="users_direction_check",
        ),
        CheckConstraint("input_mode IN ('typing', 'reveal')", name="users_input_mode_check"),
        CheckConstraint("role IN ('user', 'admin')", name="users_role_check"),
        CheckConstraint(
            "language IS NULL OR language IN ('en', 'zh-Hans', 'hi', 'es', 'de')",
            name="users_language_check",
        ),
        CheckConstraint("email = lower(email)", name="users_email_normalized_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="user")
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    daily_goal: Mapped[int] = mapped_column(Integer, default=12)
    direction: Mapped[str] = mapped_column(String(16), default="forward")
    input_mode: Mapped[str] = mapped_column(String(16), default="typing")
    selected_deck_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("decks.id", ondelete="SET NULL"), nullable=True
    )
    selected_section_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Deck(Base):
    __tablename__ = "decks"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="decks_status_check"),
        CheckConstraint("version >= 1", name="decks_version_check"),
        UniqueConstraint("sort_order", name="uq_decks_sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    front_label: Mapped[str] = mapped_column(String(80))
    back_label: Mapped[str] = mapped_column(String(80))
    front_language: Mapped[str] = mapped_column(String(35))
    back_language: Mapped[str] = mapped_column(String(35))
    front_matcher: Mapped[str] = mapped_column(String(32), default="generic-v1")
    back_matcher: Mapped[str] = mapped_column(String(32), default="generic-v1")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    license: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("deck_id", "stable_key", name="uq_sections_deck_key"),
        UniqueConstraint("deck_id", "sort_order", name="uq_sections_deck_order"),
        Index("idx_sections_deck_active_order", "deck_id", "active", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deck_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("decks.id", ondelete="CASCADE"), index=True
    )
    stable_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("deck_id", "stable_key", name="uq_cards_deck_key"),
        UniqueConstraint("deck_id", "sort_order", name="uq_cards_deck_order"),
        Index("idx_cards_deck_section_order", "deck_id", "section_id", "sort_order"),
        Index("idx_cards_deck_active", "deck_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deck_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("decks.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stable_key: Mapped[str] = mapped_column(String(160))
    sort_order: Mapped[int] = mapped_column(Integer)
    front_text: Mapped[str] = mapped_column(Text)
    back_text: Mapped[str] = mapped_column(Text)
    front_answers: Mapped[list[str]] = mapped_column(JSON, default=list)
    back_answers: Mapped[list[str]] = mapped_column(JSON, default=list)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    content_version: Mapped[int] = mapped_column(Integer, default=1)


class UserCardProgress(Base):
    __tablename__ = "user_card_progress"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('forward', 'reverse')",
            name="progress_direction_check",
        ),
        CheckConstraint(
            "phase IN ('learning', 'review', 'relearning')",
            name="progress_phase_check",
        ),
        CheckConstraint("version >= 0", name="progress_version_check"),
        CheckConstraint("ease BETWEEN 1.3 AND 3.0", name="progress_ease_check"),
        CheckConstraint("interval_days BETWEEN 0 AND 730", name="progress_interval_check"),
        CheckConstraint("repetitions >= 0", name="progress_repetitions_check"),
        CheckConstraint("lapses >= 0", name="progress_lapses_check"),
        CheckConstraint(
            "last_rating IS NULL OR last_rating BETWEEN 0 AND 3",
            name="progress_last_rating_check",
        ),
        Index("idx_progress_user_due", "user_id", "due_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    direction: Mapped[str] = mapped_column(String(16), primary_key=True)
    phase: Mapped[str] = mapped_column(String(16), default="learning")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('forward', 'reverse', 'mixed')",
            name="study_sessions_direction_check",
        ),
        CheckConstraint(
            "input_mode IN ('typing', 'reveal')",
            name="study_sessions_input_mode_check",
        ),
        CheckConstraint("target_count BETWEEN 1 AND 50", name="study_sessions_target_check"),
        Index("idx_study_sessions_user_started", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    deck_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("decks.id", ondelete="RESTRICT"))
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    direction: Mapped[str] = mapped_column(String(16))
    input_mode: Mapped[str] = mapped_column(String(16))
    target_count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StudySessionItem(Base):
    __tablename__ = "study_session_items"
    __table_args__ = (
        UniqueConstraint("session_id", "ordinal", name="uq_study_session_ordinal"),
        UniqueConstraint("session_id", "card_id", "direction", name="uq_study_session_card"),
        CheckConstraint(
            "direction IN ('forward', 'reverse')",
            name="study_items_direction_check",
        ),
        CheckConstraint("ordinal >= 1", name="study_items_ordinal_check"),
        CheckConstraint("base_version >= 0", name="study_items_base_version_check"),
        CheckConstraint(
            "(checked_answer_hash IS NULL AND checked_correct IS NULL) OR "
            "(checked_answer_hash IS NOT NULL AND checked_correct IS NOT NULL)",
            name="study_items_check_result_consistent",
        ),
        Index("idx_study_session_items_session", "session_id", "ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("study_sessions.id", ondelete="CASCADE")
    )
    card_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cards.id", ondelete="RESTRICT"))
    ordinal: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(16))
    base_version: Mapped[int] = mapped_column(Integer)
    prompt_snapshot: Mapped[str] = mapped_column(Text)
    solution_snapshot: Mapped[str] = mapped_column(Text)
    accepted_answers_snapshot: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    prompt_language: Mapped[str] = mapped_column(String(35))
    answer_language: Mapped[str] = mapped_column(String(35))
    matcher_profile: Mapped[str] = mapped_column(String(32), default="generic-v1")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_answer_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checked_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_reviews_user_idempotency"),
        UniqueConstraint(
            "user_id",
            "card_id",
            "direction",
            "base_version",
            name="uq_reviews_state_version",
        ),
        UniqueConstraint("session_item_id", name="uq_reviews_session_item"),
        CheckConstraint("rating BETWEEN 0 AND 3", name="reviews_rating_check"),
        CheckConstraint(
            "direction IN ('forward', 'reverse')",
            name="reviews_direction_check",
        ),
        CheckConstraint("mode IN ('typing', 'self_assessment')", name="reviews_mode_check"),
        CheckConstraint("base_version >= 0", name="reviews_base_version_check"),
        CheckConstraint(
            "response_ms IS NULL OR response_ms BETWEEN 0 AND 600000",
            name="reviews_response_ms_check",
        ),
        Index("idx_reviews_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("study_session_items.id", ondelete="CASCADE")
    )
    idempotency_key: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cards.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(16))
    base_version: Mapped[int] = mapped_column(Integer)
    rating: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(24))
    was_correct: Mapped[bool] = mapped_column(Boolean)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer: Mapped[str | None] = mapped_column(String(250), nullable=True)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response_json: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeckVersion(Base):
    __tablename__ = "deck_versions"
    __table_args__ = (
        UniqueConstraint("deck_id", "version", name="uq_deck_versions_version"),
        UniqueConstraint("deck_id", "sha256", name="uq_deck_versions_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deck_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("decks.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    item_count: Mapped[int] = mapped_column(Integer)
    warnings: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
