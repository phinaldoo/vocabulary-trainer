from fastapi import APIRouter, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.dependencies import CurrentAuthWithCsrf, Database, SettingsDependency
from app.errors import ApiError
from app.models import Deck, Section, User
from app.schemas import (
    AccountDeleteRequest,
    AccountProfileUpdate,
    LanguageUpdate,
    SettingsUpdate,
    UserPublic,
)
from app.security import clear_auth_cookies, normalize_email, verify_password

router = APIRouter(prefix="/account", tags=["account"])


@router.patch("/profile", response_model=UserPublic)
async def update_profile(
    payload: AccountProfileUpdate,
    response: Response,
    auth: CurrentAuthWithCsrf,
    db: Database,
) -> User:
    user = auth.user
    email = normalize_email(str(payload.email))
    if email != user.email:
        existing_user = await db.scalar(
            select(User.id).where(User.email == email, User.id != user.id)
        )
        if existing_user:
            raise ApiError(409, "email_in_use", "Diese E-Mail-Adresse wird bereits verwendet.")

    user.email = email
    user.display_name = payload.display_name
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            409,
            "email_in_use",
            "Diese E-Mail-Adresse wird bereits verwendet.",
        ) from exc
    await db.refresh(user)
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.patch("/settings", response_model=UserPublic)
async def update_settings(
    payload: SettingsUpdate,
    response: Response,
    auth: CurrentAuthWithCsrf,
    db: Database,
) -> User:
    user = auth.user
    user.daily_goal = payload.daily_goal
    user.direction = payload.direction
    user.input_mode = payload.input_mode
    if payload.language is not None:
        user.language = payload.language
    if payload.selected_deck_id is not None:
        deck = await db.scalar(
            select(Deck).where(
                Deck.id == payload.selected_deck_id,
                Deck.status == "published",
            )
        )
        if not deck:
            raise ApiError(404, "deck_not_found", "Dieses Deck ist nicht veröffentlicht.")
    if payload.selected_section_id is not None:
        section = await db.scalar(
            select(Section).where(
                Section.id == payload.selected_section_id,
                Section.deck_id == payload.selected_deck_id,
                Section.active.is_(True),
            )
        )
        if not section:
            raise ApiError(404, "section_not_found", "Dieser Abschnitt gehört nicht zum Deck.")
    user.selected_deck_id = payload.selected_deck_id
    user.selected_section_id = payload.selected_section_id
    await db.commit()
    await db.refresh(user)
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.post("/language/initialize", response_model=UserPublic)
async def initialize_language(
    payload: LanguageUpdate,
    response: Response,
    auth: CurrentAuthWithCsrf,
    db: Database,
) -> User:
    """Set an existing account's language once without overwriting a user choice."""
    user = auth.user
    if user.language is None:
        await db.execute(
            update(User)
            .where(User.id == user.id, User.language.is_(None))
            .values(language=payload.language)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        await db.refresh(user)
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: AccountDeleteRequest,
    response: Response,
    auth: CurrentAuthWithCsrf,
    db: Database,
    settings: SettingsDependency,
) -> None:
    if not await run_in_threadpool(verify_password, payload.password, auth.user.password_hash):
        raise ApiError(403, "password_invalid", "Das Passwort ist nicht korrekt.")
    await db.execute(delete(User).where(User.id == auth.user.id))
    await db.commit()
    clear_auth_cookies(response, settings)
