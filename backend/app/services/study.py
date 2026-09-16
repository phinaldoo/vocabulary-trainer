from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import (
    Card,
    Deck,
    ReviewEvent,
    Section,
    StudySession,
    StudySessionItem,
    User,
    UserCardProgress,
)
from app.schemas import StudyCard, StudySessionCreate, StudySessionPublic


def direction_for(card: Card, setting: str) -> str:
    if setting != "mixed":
        return setting
    return "forward" if card.sort_order % 2 else "reverse"


def side_snapshot(card: Card, deck: Deck, direction: str) -> dict[str, object]:
    if direction == "forward":
        return {
            "prompt": card.front_text,
            "solution": card.back_text,
            "accepted_answers": card.back_answers,
            "prompt_language": deck.front_language,
            "answer_language": deck.back_language,
            "matcher_profile": deck.back_matcher,
        }
    return {
        "prompt": card.back_text,
        "solution": card.front_text,
        "accepted_answers": card.front_answers,
        "prompt_language": deck.back_language,
        "answer_language": deck.front_language,
        "matcher_profile": deck.front_matcher,
    }


def adaptive_weight(progress: UserCardProgress | None) -> float:
    """Favor unknown/hard cards; successful repetition lowers, never removes, probability."""
    if progress is None:
        return 4.0
    if progress.last_rating == 0:
        return 8.0
    if progress.last_rating == 1:
        return 6.0
    return max(0.25, 4.0 / (1 + progress.repetitions))


def random_selection(
    cards: list[Card],
    progress_map: dict[tuple[uuid.UUID, str], UserCardProgress],
    payload: StudySessionCreate,
) -> list[tuple[Card, str, int]]:
    # An exponential race samples without replacement in weighted random order.
    # In mixed mode, average both directions for card selection, then favor the
    # weaker direction. Each vocabulary appears at most once in a session.
    candidates = []
    for card in cards:
        directions = ["forward", "reverse"] if payload.direction == "mixed" else [payload.direction]
        weights = [
            adaptive_weight(progress_map.get((card.id, direction)))
            if payload.selection_mode == "adaptive"
            else 1.0
            for direction in directions
        ]
        direction = random.choices(directions, weights=weights, k=1)[0]
        progress = progress_map.get((card.id, direction))
        priority = random.expovariate(sum(weights) / len(weights))
        candidates.append((priority, card, direction, progress.version if progress else 0))
    candidates.sort(key=lambda candidate: candidate[0])
    return [
        (card, direction, version) for _, card, direction, version in candidates[: payload.limit]
    ]


async def create_study_session(
    db: AsyncSession,
    user: User,
    payload: StudySessionCreate,
) -> StudySessionPublic:
    deck = await db.scalar(
        select(Deck).where(Deck.id == payload.deck_id, Deck.status == "published")
    )
    if not deck:
        raise ApiError(404, "deck_not_found", "Dieses Deck ist nicht veröffentlicht.")
    section_ids = payload.section_ids or []
    if section_ids:
        valid_ids = set(await db.scalars(
            select(Section.id).where(
                Section.id.in_(section_ids),
                Section.deck_id == deck.id,
                Section.active.is_(True),
            )
        ))
        if valid_ids != set(section_ids):
            raise ApiError(404, "section_not_found", "Dieser Abschnitt gehört nicht zum Deck.")

    card_query = select(Card).where(Card.deck_id == deck.id, Card.active.is_(True))
    if section_ids:
        card_query = card_query.where(Card.section_id.in_(section_ids))
    cards = list((await db.scalars(card_query.order_by(Card.sort_order))).all())
    if not cards:
        raise ApiError(409, "no_cards", "Für diese Auswahl sind keine Karten veröffentlicht.")

    ids = [card.id for card in cards]
    progress = list(
        (
            await db.scalars(
                select(UserCardProgress).where(
                    UserCardProgress.user_id == user.id,
                    UserCardProgress.card_id.in_(ids),
                )
            )
        ).all()
    )
    progress_map = {(row.card_id, row.direction): row for row in progress}
    by_id = {card.id: card for card in cards}
    now = datetime.now(UTC)

    due = [
        row
        for row in progress
        if _aware(row.due_at) <= now
        and (payload.direction == "mixed" or row.direction == payload.direction)
    ]
    due.sort(key=lambda row: _aware(row.due_at))

    selected: list[tuple[Card, str, int]] = []
    selected_keys: set[tuple[uuid.UUID, str]] = set()
    selected_card_ids: set[uuid.UUID] = set()
    if payload.selection_mode == "scheduled":
        for row in due:
            card = by_id.get(row.card_id)
            key = (row.card_id, row.direction)
            if not card or key in selected_keys or card.id in selected_card_ids:
                continue
            selected.append((card, row.direction, row.version))
            selected_keys.add(key)
            selected_card_ids.add(card.id)
            if len(selected) == payload.limit:
                break

        if len(selected) < payload.limit:
            for card in cards:
                direction = direction_for(card, payload.direction)
                key = (card.id, direction)
                if card.id in selected_card_ids or key in selected_keys or key in progress_map:
                    continue
                selected.append((card, direction, 0))
                selected_keys.add(key)
                selected_card_ids.add(card.id)
                if len(selected) == payload.limit:
                    break
    else:
        selected = random_selection(cards, progress_map, payload)

    study_session = StudySession(
        user_id=user.id,
        deck_id=deck.id,
        section_id=payload.section_id,
        section_ids=[str(value) for value in section_ids],
        direction=payload.direction,
        input_mode=payload.input_mode,
        selection_mode=payload.selection_mode,
        target_count=payload.limit,
        completed_at=now if not selected else None,
    )
    db.add(study_session)
    await db.flush()

    for ordinal, (card, direction, version) in enumerate(selected, start=1):
        snapshot = side_snapshot(card, deck, direction)
        db.add(
            StudySessionItem(
                session_id=study_session.id,
                card_id=card.id,
                ordinal=ordinal,
                direction=direction,
                base_version=version,
                prompt_snapshot=str(snapshot["prompt"]),
                solution_snapshot=str(snapshot["solution"]),
                accepted_answers_snapshot=list(snapshot["accepted_answers"]),
                metadata_snapshot=card.details,
                prompt_language=str(snapshot["prompt_language"]),
                answer_language=str(snapshot["answer_language"]),
                matcher_profile=str(snapshot["matcher_profile"]),
            )
        )

    user.selected_deck_id = deck.id
    user.selected_section_id = payload.section_id
    user.selected_section_ids = [str(value) for value in section_ids]
    user.direction = payload.direction
    user.input_mode = payload.input_mode
    await db.commit()
    return await get_study_session(db, user.id, study_session.id)


async def get_study_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> StudySessionPublic:
    session_row = (
        await db.execute(
            select(StudySession, Deck, Section.title)
            .join(Deck, Deck.id == StudySession.deck_id)
            .outerjoin(Section, Section.id == StudySession.section_id)
            .where(StudySession.id == session_id, StudySession.user_id == user_id)
        )
    ).first()
    if not session_row:
        raise ApiError(404, "study_session_not_found", "Diese Lerneinheit gibt es nicht.")
    study_session, deck, selected_section_title = session_row

    section_ids = (
        [uuid.UUID(value) for value in study_session.section_ids]
        if study_session.section_ids is not None
        else [study_session.section_id] if study_session.section_id else []
    )
    titles = dict((await db.execute(
        select(Section.id, Section.title).where(Section.id.in_(section_ids))
    )).all())
    section_titles = [titles[value] for value in section_ids if value in titles]

    rows = (
        await db.execute(
            select(StudySessionItem, Card.section_id, Section.title)
            .join(Card, Card.id == StudySessionItem.card_id)
            .outerjoin(Section, Section.id == Card.section_id)
            .where(StudySessionItem.session_id == session_id)
            .order_by(StudySessionItem.ordinal)
        )
    ).all()
    reviewed = sum(1 for item, _, _ in rows if item.reviewed_at is not None)
    correct_reviewed = int(
        await db.scalar(
            select(func.count())
            .select_from(ReviewEvent)
            .join(StudySessionItem, StudySessionItem.id == ReviewEvent.session_item_id)
            .where(
                StudySessionItem.session_id == session_id,
                ReviewEvent.was_correct.is_(True),
            )
        )
        or 0
    )
    cards = [
        StudyCard(
            item_id=item.id,
            card_id=item.card_id,
            section_id=section_id,
            section_title=section_title,
            ordinal=item.ordinal,
            direction=item.direction,
            prompt=item.prompt_snapshot,
            prompt_language=item.prompt_language,
            answer_language=item.answer_language,
            metadata=item.metadata_snapshot,
            state_version=item.base_version,
            is_new=item.base_version == 0,
        )
        for item, section_id, section_title in rows
        if item.reviewed_at is None
    ]
    return StudySessionPublic(
        selection_mode=study_session.selection_mode,
        id=study_session.id,
        deck_id=deck.id,
        deck_title=deck.title,
        section_id=study_session.section_id,
        section_title=selected_section_title,
        section_ids=section_ids,
        section_titles=section_titles,
        front_label=deck.front_label,
        back_label=deck.back_label,
        front_language=deck.front_language,
        back_language=deck.back_language,
        direction=study_session.direction,
        input_mode=study_session.input_mode,
        total=len(rows),
        reviewed=reviewed,
        correct_reviewed=correct_reviewed,
        complete=reviewed == len(rows),
        cards=cards,
    )


async def get_owned_item(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> tuple[StudySession, StudySessionItem]:
    query = (
        select(StudySession, StudySessionItem)
        .join(StudySessionItem, StudySessionItem.session_id == StudySession.id)
        .where(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
            StudySessionItem.id == item_id,
        )
    )
    if for_update:
        query = query.with_for_update(of=StudySessionItem)
    row = (await db.execute(query)).first()
    if not row:
        raise ApiError(404, "study_item_not_found", "Diese Lernkarte gibt es nicht.")
    return row


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
