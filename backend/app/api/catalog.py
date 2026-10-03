import math
import uuid
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentAuth, CurrentAuthWithCsrf, Database
from app.errors import ApiError
from app.models import Card, Deck, Section, UserCardPreference, UserCardProgress, UserFavorite
from app.schemas import CardPublic, DeckPublic, DifficultyUpdate, PaginatedCards, SectionPublic
from app.services.analytics import progress_data
from app.services.catalogue import deck_public, published_decks, resolve_published_deck

router = APIRouter(tags=["catalog"])


@router.get("/decks", response_model=list[DeckPublic])
async def deck_list(auth: CurrentAuth, db: Database, response: Response) -> list[DeckPublic]:
    del auth
    response.headers["Cache-Control"] = "private, no-store"
    return [await deck_public(db, deck) for deck in await published_decks(db)]


@router.get("/sections", response_model=list[SectionPublic])
async def section_list(
    auth: CurrentAuth,
    db: Database,
    response: Response,
    deck_id: uuid.UUID | None = None,
) -> list[SectionPublic]:
    deck = await resolve_published_deck(db, deck_id or auth.user.selected_deck_id)
    response.headers["Cache-Control"] = "private, no-store"
    if not deck:
        return []
    return (await progress_data(db, auth.user, deck.id)).sections


@router.get("/cards", response_model=PaginatedCards)
async def card_list(
    auth: CurrentAuth,
    db: Database,
    response: Response,
    deck_id: uuid.UUID | None = None,
    q: str = Query(default="", max_length=100),
    section_id: uuid.UUID | None = None,
    state: str = Query(
        default="all",
        pattern="^(all|new|learning|familiar|mastered|difficult|favorites)$",
    ),
    sort_by: Literal[
        "original", "front", "back", "section", "gender", "part_of_speech",
        "additional_info", "additional_info_2", "difficulty", "status",
    ] = "original",
    sort_direction: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=36, ge=1, le=100),
) -> PaginatedCards:
    deck = await resolve_published_deck(db, deck_id or auth.user.selected_deck_id)
    if not deck:
        return PaginatedCards(items=[], page=page, page_size=page_size, total=0, pages=1)
    if section_id:
        section = await db.scalar(
            select(Section).where(
                Section.id == section_id,
                Section.deck_id == deck.id,
                Section.active.is_(True),
            )
        )
        if not section:
            raise ApiError(404, "section_not_found", "Dieser Abschnitt gehört nicht zum Deck.")

    progress_subquery = (
        select(
            UserCardProgress.card_id.label("card_id"),
            func.min(UserCardProgress.interval_days).label("interval_days"),
            func.min(UserCardProgress.repetitions).label("repetitions"),
            func.max(UserCardProgress.lapses).label("lapses"),
            func.min(UserCardProgress.last_rating).label("last_rating"),
        )
        .where(UserCardProgress.user_id == auth.user.id)
        .group_by(UserCardProgress.card_id)
        .subquery()
    )
    favorite_subquery = (
        select(UserFavorite.card_id).where(UserFavorite.user_id == auth.user.id).subquery()
    )
    preference_subquery = (
        select(UserCardPreference.card_id, UserCardPreference.difficulty)
        .where(UserCardPreference.user_id == auth.user.id).subquery()
    )
    difficulty = func.coalesce(preference_subquery.c.difficulty, "auto")
    item_state = case(
        (progress_subquery.c.repetitions.is_(None), "new"),
        (
            (func.coalesce(progress_subquery.c.lapses, 0) > 0)
            | progress_subquery.c.last_rating.in_((0, 1)),
            "difficult",
        ),
        (progress_subquery.c.repetitions == 0, "new"),
        (progress_subquery.c.interval_days >= 21, "mastered"),
        (progress_subquery.c.interval_days >= 3, "familiar"),
        else_="learning",
    ).label("status")
    query = (
        select(
            Card,
            Section.title,
            favorite_subquery.c.card_id.label("favorite_id"),
            item_state,
            difficulty,
        )
        .outerjoin(Section, Section.id == Card.section_id)
        .outerjoin(preference_subquery, preference_subquery.c.card_id == Card.id)
        .outerjoin(progress_subquery, progress_subquery.c.card_id == Card.id)
        .outerjoin(favorite_subquery, favorite_subquery.c.card_id == Card.id)
        .where(Card.active.is_(True), Card.deck_id == deck.id)
    )
    if section_id:
        query = query.where(Card.section_id == section_id)
    if q.strip():
        needle = f"%{q.strip()}%"
        query = query.where(Card.front_text.ilike(needle) | Card.back_text.ilike(needle))
    if state == "favorites":
        query = query.where(favorite_subquery.c.card_id.is_not(None))
    elif state == "difficult":
        query = query.where(
            (difficulty == "hard") | ((difficulty == "auto") & (item_state == "difficult"))
        )
    elif state != "all":
        query = query.where(item_state == state)

    metadata_keys = {
        "gender": ("gender", "genus"),
        "part_of_speech": ("part_of_speech", "partOfSpeech", "wortart"),
        "additional_info": ("additional_info", "info", "zusatzinformation"),
        "additional_info_2": ("additional_info_2", "note", "zusatzinformation2"),
    }
    difficulty_order = case(
        (difficulty == "easy", 0), (difficulty == "normal", 1), (difficulty == "hard", 2),
        (item_state == "difficult", 2), (item_state == "mastered", 0), else_=1,
    )
    if sort_by in metadata_keys:
        ordering = func.lower(func.coalesce(*[
            func.nullif(Card.details[key].as_string(), "") for key in metadata_keys[sort_by]
        ]))
    else:
        ordering = {
            "original": Card.sort_order, "front": func.lower(Card.front_text),
            "back": func.lower(Card.back_text), "section": Section.sort_order,
            "difficulty": difficulty_order, "status": item_state,
        }[sort_by]
    ordering = ordering.desc() if sort_direction == "desc" else ordering.asc()
    query = query.order_by(ordering.nulls_last(), Card.sort_order, Card.id)

    total = int(
        await db.scalar(
            select(func.count()).select_from(
                query.with_only_columns(Card.id).order_by(None).subquery()
            )
        )
        or 0
    )
    start = (page - 1) * page_size
    rows = (await db.execute(query.offset(start).limit(page_size))).all()
    items = [
        CardPublic.model_validate(card).model_copy(
            update={
                "section_title": section_title,
                "favorite": favorite_id is not None,
                "status": item_state,
                "difficulty": card_difficulty,
            }
        )
        for card, section_title, favorite_id, item_state, card_difficulty in rows
    ]
    response.headers["Cache-Control"] = "private, no-store"
    return PaginatedCards(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.put("/favorites/{card_id}", status_code=status.HTTP_200_OK)
async def add_favorite(
    card_id: uuid.UUID,
    auth: CurrentAuthWithCsrf,
    db: Database,
) -> dict[str, bool]:
    card = await db.scalar(
        select(Card)
        .join(Deck, Deck.id == Card.deck_id)
        .where(Card.id == card_id, Card.active.is_(True), Deck.status == "published")
    )
    if not card:
        raise ApiError(404, "card_not_found", "Diese Karte gibt es nicht.")
    if not await db.get(UserFavorite, (auth.user.id, card_id)):
        db.add(UserFavorite(user_id=auth.user.id, card_id=card_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return {"favorite": True}


@router.delete("/favorites/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    card_id: uuid.UUID,
    auth: CurrentAuthWithCsrf,
    db: Database,
) -> None:
    favorite = await db.get(UserFavorite, (auth.user.id, card_id))
    if favorite:
        await db.delete(favorite)
        await db.commit()


@router.put("/cards/{card_id}/difficulty", response_model=DifficultyUpdate)
async def set_card_difficulty(
    card_id: uuid.UUID,
    payload: DifficultyUpdate,
    auth: CurrentAuthWithCsrf,
    db: Database,
) -> DifficultyUpdate:
    card = await db.scalar(
        select(Card).join(Deck, Deck.id == Card.deck_id)
        .where(Card.id == card_id, Card.active.is_(True), Deck.status == "published")
    )
    if not card:
        raise ApiError(404, "card_not_found", "Diese Karte gibt es nicht.")
    # Serialize preference updates for this learner, including concurrent inserts.
    from app.models import User
    await db.scalar(select(User).where(User.id == auth.user.id).with_for_update())
    preference = await db.get(UserCardPreference, (auth.user.id, card_id))
    if payload.difficulty == "auto":
        if preference:
            await db.delete(preference)
    elif preference:
        preference.difficulty = payload.difficulty
    else:
        db.add(UserCardPreference(user_id=auth.user.id, card_id=card_id,
                                  difficulty=payload.difficulty))
    await db.commit()
    return payload
