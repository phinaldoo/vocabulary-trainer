import math
import uuid

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentAuth, CurrentAuthWithCsrf, Database
from app.errors import ApiError
from app.models import Card, Deck, Section, UserCardProgress, UserFavorite
from app.schemas import CardPublic, DeckPublic, PaginatedCards, SectionPublic
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
        )
        .outerjoin(Section, Section.id == Card.section_id)
        .outerjoin(progress_subquery, progress_subquery.c.card_id == Card.id)
        .outerjoin(favorite_subquery, favorite_subquery.c.card_id == Card.id)
        .where(Card.active.is_(True), Card.deck_id == deck.id)
        .order_by(Card.sort_order)
    )
    if section_id:
        query = query.where(Card.section_id == section_id)
    if q.strip():
        needle = f"%{q.strip()}%"
        query = query.where(Card.front_text.ilike(needle) | Card.back_text.ilike(needle))
    if state == "favorites":
        query = query.where(favorite_subquery.c.card_id.is_not(None))
    elif state != "all":
        query = query.where(item_state == state)

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
            }
        )
        for card, section_title, favorite_id, item_state in rows
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
