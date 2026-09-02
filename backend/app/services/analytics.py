from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, ReviewEvent, Section, User, UserCardProgress
from app.schemas import DashboardData, DifficultCard, ProgressData, SectionPublic, WeeklyActivity
from app.services.catalogue import deck_public, resolve_published_deck

BERLIN = ZoneInfo("Europe/Berlin")


def _day_key(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(BERLIN).date().isoformat()


def _streak(reviews: list[ReviewEvent], now: datetime) -> int:
    active = {_day_key(review.created_at) for review in reviews}
    reference = now.astimezone(BERLIN).date()
    if reference.isoformat() not in active:
        reference -= timedelta(days=1)
    count = 0
    while reference.isoformat() in active:
        count += 1
        reference -= timedelta(days=1)
    return count


async def _base_data(
    db: AsyncSession,
    user_id: uuid.UUID,
    deck_id: uuid.UUID,
    review_days: int,
) -> tuple[list[Card], list[UserCardProgress], list[ReviewEvent]]:
    since = datetime.now(UTC) - timedelta(days=review_days)
    cards = list(
        (
            await db.scalars(
                select(Card)
                .where(Card.deck_id == deck_id, Card.active.is_(True))
                .order_by(Card.sort_order)
            )
        ).all()
    )
    progress = list(
        (
            await db.scalars(
                select(UserCardProgress)
                .join(Card, Card.id == UserCardProgress.card_id)
                .where(
                    UserCardProgress.user_id == user_id,
                    Card.deck_id == deck_id,
                    Card.active.is_(True),
                )
            )
        ).all()
    )
    reviews = list(
        (
            await db.scalars(
                select(ReviewEvent)
                .join(Card, Card.id == ReviewEvent.card_id)
                .where(
                    ReviewEvent.user_id == user_id,
                    ReviewEvent.created_at >= since,
                    Card.deck_id == deck_id,
                )
                .order_by(ReviewEvent.created_at.desc())
                .limit(10_000)
            )
        ).all()
    )
    return cards, progress, reviews


async def dashboard_data(
    db: AsyncSession,
    user: User,
    deck_id: uuid.UUID | None = None,
) -> DashboardData:
    deck = await resolve_published_deck(db, deck_id or user.selected_deck_id)
    if not deck:
        return DashboardData(
            deck=None,
            due_count=0,
            reviewed_today=0,
            learned_count=0,
            mastered_count=0,
            streak=0,
            total_count=0,
            progress_percent=0,
            weekly_activity=[],
            difficult=[],
        )
    cards, progress, reviews = await _base_data(db, user.id, deck.id, 370)
    now = datetime.now(UTC)
    today = _day_key(now)
    learned_ids = {row.card_id for row in progress}
    due_progress = sum(1 for row in progress if _aware(row.due_at) <= now)
    unseen_available = max(0, len(cards) - len(learned_ids))
    due_count = min(user.daily_goal, due_progress + unseen_available)
    reviewed_today = sum(1 for review in reviews if _day_key(review.created_at) == today)

    best_progress: dict[uuid.UUID, UserCardProgress] = {}
    for row in progress:
        current = best_progress.get(row.card_id)
        if not current or row.interval_days > current.interval_days:
            best_progress[row.card_id] = row

    difficult_rows = sorted(
        [row for row in progress if row.lapses > 0 or row.last_rating in {0, 1}],
        key=lambda row: (row.lapses, row.last_reviewed_at or datetime.min.replace(tzinfo=UTC)),
        reverse=True,
    )
    by_id = {item.id: item for item in cards}
    section_ids = {card.section_id for card in cards if card.section_id}
    section_titles = (
        {
            section.id: section.title
            for section in (
                await db.scalars(select(Section).where(Section.id.in_(section_ids)))
            ).all()
        }
        if section_ids
        else {}
    )
    difficult: list[DifficultCard] = []
    seen: set[uuid.UUID] = set()
    for row in difficult_rows:
        card = by_id.get(row.card_id)
        if not card or card.id in seen:
            continue
        seen.add(card.id)
        difficult.append(
            DifficultCard(
                id=card.id,
                deck_id=deck.id,
                section_id=card.section_id,
                section_title=section_titles.get(card.section_id),
                front_text=card.front_text,
                back_text=card.back_text,
                front_language=deck.front_language,
                lapses=row.lapses,
            )
        )
        if len(difficult) == 4:
            break

    days = [now - timedelta(days=offset) for offset in range(6, -1, -1)]
    weekly = []
    for day in days:
        key = _day_key(day)
        weekly.append(
            WeeklyActivity(
                date=day.astimezone(BERLIN).date(),
                count=sum(1 for review in reviews if _day_key(review.created_at) == key),
                today=key == today,
            )
        )

    mastered = sum(
        1 for row in best_progress.values() if row.interval_days >= 21 and row.repetitions >= 2
    )
    return DashboardData(
        deck=await deck_public(db, deck),
        due_count=due_count,
        reviewed_today=reviewed_today,
        learned_count=len(learned_ids),
        mastered_count=mastered,
        streak=_streak(reviews, now),
        total_count=len(cards),
        progress_percent=round(len(learned_ids) / len(cards) * 100) if cards else 0,
        weekly_activity=weekly,
        difficult=difficult,
    )


async def progress_data(
    db: AsyncSession,
    user: User,
    deck_id: uuid.UUID | None = None,
) -> ProgressData:
    deck = await resolve_published_deck(db, deck_id or user.selected_deck_id)
    if not deck:
        return ProgressData(
            deck=None,
            total=0,
            learned=0,
            secure=0,
            familiar=0,
            learning=0,
            accuracy=0,
            reviews=0,
            streak=0,
            sections=[],
        )
    cards, progress, reviews = await _base_data(db, user.id, deck.id, 90)
    now = datetime.now(UTC)
    learned_ids = {row.card_id for row in progress}
    by_section: dict[uuid.UUID | None, list[Card]] = defaultdict(list)
    for card in cards:
        by_section[card.section_id].append(card)

    best: dict[uuid.UUID, UserCardProgress] = {}
    for row in progress:
        current = best.get(row.card_id)
        if not current or row.interval_days > current.interval_days:
            best[row.card_id] = row

    section_rows = list(
        (
            await db.scalars(
                select(Section)
                .where(Section.deck_id == deck.id, Section.active.is_(True))
                .order_by(Section.sort_order)
            )
        ).all()
    )
    sections = []
    for section in section_rows:
        entries = by_section[section.id]
        learned = sum(1 for card in entries if card.id in learned_ids)
        mastered = sum(
            1 for card in entries if (state := best.get(card.id)) and state.interval_days >= 21
        )
        due = sum(
            1
            for card in entries
            if any(row.card_id == card.id and _aware(row.due_at) <= now for row in progress)
        )
        sections.append(
            SectionPublic(
                id=section.id,
                deck_id=deck.id,
                stable_key=section.stable_key,
                title=section.title,
                sort_order=section.sort_order,
                active=section.active,
                total=len(entries),
                learned=learned,
                mastered=mastered,
                due=due,
                progress_percent=round(learned / len(entries) * 100) if entries else 0,
            )
        )

    correct = sum(1 for review in reviews if review.was_correct)
    return ProgressData(
        deck=await deck_public(db, deck),
        total=len(cards),
        learned=len(learned_ids),
        secure=sum(1 for row in best.values() if row.interval_days >= 21),
        familiar=sum(1 for row in best.values() if 3 <= row.interval_days < 21),
        learning=sum(1 for row in best.values() if row.interval_days < 3),
        accuracy=round(correct / len(reviews) * 100) if reviews else 0,
        reviews=len(reviews),
        streak=_streak(reviews, now),
        sections=sections,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
