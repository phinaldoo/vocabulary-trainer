from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentAdmin, CurrentAdminWithCsrf, Database
from app.errors import ApiError
from app.models import Card, Deck, Section, User
from app.schemas import (
    AdminUserPublic,
    CardCreate,
    CardPublic,
    CardUpdate,
    DeckCreate,
    DeckManifest,
    DeckPublic,
    DeckStatusUpdate,
    DeckUpdate,
    ImportResult,
    PaginatedCards,
    PaginatedUsers,
    SectionCreate,
    SectionPublic,
    SectionUpdate,
)
from app.services.answer_matcher import validate_answer_spec
from app.services.catalogue import card_id_for_key, deck_public, import_manifest

router = APIRouter(prefix="/admin", tags=["admin"])


async def _deck_or_404(db: Database, deck_id: uuid.UUID, *, lock: bool = False) -> Deck:
    query = select(Deck).where(Deck.id == deck_id)
    if lock:
        query = query.with_for_update()
    deck = await db.scalar(query)
    if not deck:
        raise ApiError(404, "deck_not_found", "Dieses Deck gibt es nicht.")
    return deck


async def _section_or_404(db: Database, deck_id: uuid.UUID, section_id: uuid.UUID) -> Section:
    section = await db.scalar(
        select(Section).where(Section.id == section_id, Section.deck_id == deck_id)
    )
    if not section:
        raise ApiError(404, "section_not_found", "Dieser Abschnitt gehört nicht zum Deck.")
    return section


def _touch(deck: Deck) -> None:
    deck.version += 1
    deck.content_hash = None


def _validate_card(deck: Deck, payload: CardCreate | CardUpdate) -> None:
    try:
        validate_answer_spec(
            payload.front_text,
            payload.front_answers,
            matcher_profile=deck.front_matcher,
        )
        validate_answer_spec(
            payload.back_text,
            payload.back_answers,
            matcher_profile=deck.back_matcher,
        )
    except ValueError as exc:
        raise ApiError(422, "invalid_answer_spec", str(exc)) from exc


@router.get("/users", response_model=PaginatedUsers)
async def users(
    auth: CurrentAdmin,
    db: Database,
    response: Response,
    q: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PaginatedUsers:
    del auth
    conditions = []
    if q.strip():
        needle = f"%{q.strip()}%"
        conditions.append(User.display_name.ilike(needle) | User.email.ilike(needle))

    total = int(
        await db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    )
    rows = list(
        (
            await db.scalars(
                select(User)
                .where(*conditions)
                .order_by(User.created_at, User.email)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    response.headers["Cache-Control"] = "private, no-store"
    return PaginatedUsers(
        items=[AdminUserPublic.model_validate(user) for user in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/users/{user_id}/promote", response_model=AdminUserPublic)
async def promote_user(
    user_id: uuid.UUID,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> AdminUserPublic:
    del auth
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise ApiError(404, "user_not_found", "Dieses Konto gibt es nicht.")
    if user.role != "admin":
        user.role = "admin"
        await db.commit()
        await db.refresh(user)
    return AdminUserPublic.model_validate(user)


@router.get("/decks", response_model=list[DeckPublic])
async def decks(auth: CurrentAdmin, db: Database, response: Response) -> list[DeckPublic]:
    del auth
    rows = list((await db.scalars(select(Deck).order_by(Deck.sort_order))).all())
    response.headers["Cache-Control"] = "private, no-store"
    return [await deck_public(db, deck) for deck in rows]


@router.post("/decks", response_model=DeckPublic, status_code=status.HTTP_201_CREATED)
async def create_deck(
    payload: DeckCreate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> DeckPublic:
    del auth
    if await db.scalar(select(Deck.id).where(Deck.slug == payload.slug)):
        raise ApiError(409, "deck_slug_exists", "Diese Deck-ID wird bereits verwendet.")
    next_order = int(await db.scalar(select(func.max(Deck.sort_order))) or 0) + 1
    deck = Deck(**payload.model_dump(), status="draft", version=1, sort_order=next_order)
    db.add(deck)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "deck_conflict", "Das Deck konnte nicht angelegt werden.") from exc
    await db.refresh(deck)
    return await deck_public(db, deck)


@router.get("/decks/{deck_id}", response_model=DeckPublic)
async def get_deck(
    deck_id: uuid.UUID,
    auth: CurrentAdmin,
    db: Database,
) -> DeckPublic:
    del auth
    return await deck_public(db, await _deck_or_404(db, deck_id))


@router.patch("/decks/{deck_id}", response_model=DeckPublic)
async def update_deck(
    deck_id: uuid.UUID,
    payload: DeckUpdate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> DeckPublic:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    front_changed = payload.front_matcher != deck.front_matcher
    back_changed = payload.back_matcher != deck.back_matcher
    if front_changed or back_changed:
        cards = list((await db.scalars(select(Card).where(Card.deck_id == deck.id))).all())
        for card in cards:
            try:
                if front_changed:
                    validate_answer_spec(
                        card.front_text,
                        card.front_answers,
                        matcher_profile=payload.front_matcher,
                    )
                if back_changed:
                    validate_answer_spec(
                        card.back_text,
                        card.back_answers,
                        matcher_profile=payload.back_matcher,
                    )
            except ValueError as exc:
                raise ApiError(
                    422,
                    "matcher_incompatible",
                    f"Karte {card.stable_key} ist mit der neuen Auswertung ungültig: {exc}",
                ) from exc
    for name, value in payload.model_dump().items():
        setattr(deck, name, value)
    _touch(deck)
    await db.commit()
    await db.refresh(deck)
    return await deck_public(db, deck)


@router.patch("/decks/{deck_id}/status", response_model=DeckPublic)
async def update_deck_status(
    deck_id: uuid.UUID,
    payload: DeckStatusUpdate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> DeckPublic:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    if payload.status == "published":
        count = int(
            await db.scalar(
                select(func.count())
                .select_from(Card)
                .where(Card.deck_id == deck.id, Card.active.is_(True))
            )
            or 0
        )
        if count == 0:
            raise ApiError(409, "deck_empty", "Ein leeres Deck kann nicht veröffentlicht werden.")
    deck.status = payload.status
    await db.commit()
    await db.refresh(deck)
    return await deck_public(db, deck)


@router.get("/decks/{deck_id}/sections", response_model=list[SectionPublic])
async def admin_sections(
    deck_id: uuid.UUID,
    auth: CurrentAdmin,
    db: Database,
) -> list[SectionPublic]:
    del auth
    await _deck_or_404(db, deck_id)
    rows = list(
        (
            await db.scalars(
                select(Section).where(Section.deck_id == deck_id).order_by(Section.sort_order)
            )
        ).all()
    )
    results = []
    for section in rows:
        count = int(
            await db.scalar(
                select(func.count())
                .select_from(Card)
                .where(Card.section_id == section.id, Card.active.is_(True))
            )
            or 0
        )
        results.append(SectionPublic.model_validate(section).model_copy(update={"total": count}))
    return results


@router.post(
    "/decks/{deck_id}/sections",
    response_model=SectionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    deck_id: uuid.UUID,
    payload: SectionCreate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> SectionPublic:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    section = Section(deck_id=deck.id, **payload.model_dump())
    db.add(section)
    _touch(deck)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            409,
            "section_conflict",
            "Abschnitts-ID und Reihenfolge müssen innerhalb des Decks eindeutig sein.",
        ) from exc
    await db.refresh(section)
    return SectionPublic.model_validate(section)


@router.patch("/decks/{deck_id}/sections/{section_id}", response_model=SectionPublic)
async def update_section(
    deck_id: uuid.UUID,
    section_id: uuid.UUID,
    payload: SectionUpdate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> SectionPublic:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    section = await _section_or_404(db, deck_id, section_id)
    for name, value in payload.model_dump().items():
        setattr(section, name, value)
    _touch(deck)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "section_conflict", "Diese Reihenfolge ist bereits vergeben.") from exc
    await db.refresh(section)
    return SectionPublic.model_validate(section)


@router.get("/decks/{deck_id}/cards", response_model=PaginatedCards)
async def admin_cards(
    deck_id: uuid.UUID,
    auth: CurrentAdmin,
    db: Database,
    q: str = Query(default="", max_length=100),
    section_id: uuid.UUID | None = None,
    include_archived: bool = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedCards:
    del auth
    await _deck_or_404(db, deck_id)
    conditions = [Card.deck_id == deck_id]
    if not include_archived:
        conditions.append(Card.active.is_(True))
    if section_id:
        conditions.append(Card.section_id == section_id)
    if q.strip():
        needle = f"%{q.strip()}%"
        conditions.append(Card.front_text.ilike(needle) | Card.back_text.ilike(needle))

    total = int(
        await db.scalar(select(func.count()).select_from(Card).where(*conditions)) or 0
    )
    start = (page - 1) * page_size
    query = (
        select(Card, Section.title)
        .outerjoin(Section, Section.id == Card.section_id)
        .where(*conditions)
        .order_by(Card.sort_order)
        .offset(start)
        .limit(page_size)
    )
    rows = (await db.execute(query)).all()
    items = [
        CardPublic.model_validate(card).model_copy(update={"section_title": section_title})
        for card, section_title in rows
    ]
    return PaginatedCards(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/decks/{deck_id}/cards",
    response_model=CardPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_card(
    deck_id: uuid.UUID,
    payload: CardCreate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> CardPublic:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    if payload.section_id:
        await _section_or_404(db, deck.id, payload.section_id)
    _validate_card(deck, payload)
    card = Card(
        id=card_id_for_key(deck.id, payload.stable_key),
        deck_id=deck.id,
        stable_key=payload.stable_key,
        section_id=payload.section_id,
        sort_order=payload.sort_order,
        front_text=payload.front_text,
        back_text=payload.back_text,
        front_answers=payload.front_answers,
        back_answers=payload.back_answers,
        details=payload.metadata,
        active=True,
        content_version=deck.version + 1,
    )
    db.add(card)
    _touch(deck)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            409,
            "card_conflict",
            "Karten-ID und Reihenfolge müssen innerhalb des Decks eindeutig sein.",
        ) from exc
    await db.refresh(card)
    return CardPublic.model_validate(card)


@router.patch("/decks/{deck_id}/cards/{card_id}", response_model=CardPublic)
async def update_card(
    deck_id: uuid.UUID,
    card_id: uuid.UUID,
    payload: CardUpdate,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> CardPublic:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    card = await db.scalar(
        select(Card).where(Card.id == card_id, Card.deck_id == deck.id).with_for_update()
    )
    if not card:
        raise ApiError(404, "card_not_found", "Diese Karte gibt es nicht.")
    if payload.section_id:
        await _section_or_404(db, deck.id, payload.section_id)
    _validate_card(deck, payload)
    card.section_id = payload.section_id
    card.sort_order = payload.sort_order
    card.front_text = payload.front_text
    card.back_text = payload.back_text
    card.front_answers = payload.front_answers
    card.back_answers = payload.back_answers
    card.details = payload.metadata
    card.active = payload.active
    _touch(deck)
    card.content_version = deck.version
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "card_conflict", "Diese Reihenfolge ist bereits vergeben.") from exc
    await db.refresh(card)
    section_title = None
    if card.section_id:
        section_title = await db.scalar(select(Section.title).where(Section.id == card.section_id))
    return CardPublic.model_validate(card).model_copy(update={"section_title": section_title})


@router.delete(
    "/decks/{deck_id}/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def archive_card(
    deck_id: uuid.UUID,
    card_id: uuid.UUID,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> Response:
    del auth
    deck = await _deck_or_404(db, deck_id, lock=True)
    card = await db.scalar(select(Card).where(Card.id == card_id, Card.deck_id == deck.id))
    if not card:
        raise ApiError(404, "card_not_found", "Diese Karte gibt es nicht.")
    card.active = False
    _touch(deck)
    card.content_version = deck.version
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import", response_model=ImportResult)
async def import_deck(
    payload: DeckManifest,
    auth: CurrentAdminWithCsrf,
    db: Database,
) -> ImportResult:
    del auth
    return await import_manifest(db, payload)
