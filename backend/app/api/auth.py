import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.dependencies import (
    CurrentAuth,
    CurrentAuthWithCsrf,
    Database,
    SettingsDependency,
)
from app.errors import ApiError
from app.languages import request_ui_language
from app.models import Session, User
from app.schemas import LoginRequest, RegisterRequest, UserPublic
from app.security import (
    clear_auth_cookies,
    create_session,
    hash_password,
    hash_token,
    normalize_email,
    session_cookie_name,
    set_csrf_cookie,
    set_session_cookie,
    verify_double_submit_csrf,
    verify_password,
    verify_same_site_request,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/csrf")
async def csrf(
    request: Request,
    response: Response,
    db: Database,
    settings: SettingsDependency,
) -> dict[str, str]:
    verify_same_site_request(request, settings)
    token = secrets.token_urlsafe(32)
    raw_session = request.cookies.get(session_cookie_name(settings))
    if raw_session:
        active_session = await db.scalar(
            select(Session).where(Session.token_hash == hash_token(raw_session))
        )
        if active_session:
            active_session.csrf_hash = hash_token(token)
            await db.commit()
    set_csrf_cookie(response, settings, token)
    response.headers["Cache-Control"] = "private, no-store"
    return {"csrf_token": token}


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Database,
    settings: SettingsDependency,
) -> User:
    csrf_token = verify_double_submit_csrf(request, settings)
    email = normalize_email(str(payload.email))
    encoded_password = await run_in_threadpool(hash_password, payload.password)

    # PostgreSQL is the supported deployment database. Serializing registrations
    # keeps two simultaneous first sign-ups from both claiming the administrator
    # role. SQLite is used by the test suite, where registrations are sequential.
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))

    if await db.scalar(select(User.id).where(User.email == email)):
        raise ApiError(409, "registration_failed", "Das Konto konnte nicht erstellt werden.")

    is_first_user = await db.scalar(select(User.id).limit(1)) is None

    user = User(
        email=email,
        password_hash=encoded_password,
        display_name=payload.display_name,
        language=request_ui_language(payload.language, request.headers.get("accept-language")),
        role="admin" if is_first_user else "user",
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            409, "registration_failed", "Das Konto konnte nicht erstellt werden."
        ) from exc
    raw_token, csrf_token = await create_session(db, user, settings, csrf_token)
    await db.commit()
    await db.refresh(user)
    set_session_cookie(response, settings, raw_token)
    set_csrf_cookie(response, settings, csrf_token)
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.post("/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Database,
    settings: SettingsDependency,
) -> User:
    csrf_token = verify_double_submit_csrf(request, settings)
    email = normalize_email(str(payload.email))
    user = await db.scalar(select(User).where(User.email == email))
    if user:
        valid_password = await run_in_threadpool(
            verify_password, payload.password, user.password_hash
        )
    else:
        # Keep the expensive Argon2 path for unknown users to reduce timing leaks.
        await run_in_threadpool(hash_password, payload.password)
        valid_password = False
    if not user or not valid_password:
        raise ApiError(401, "invalid_credentials", "E-Mail-Adresse oder Passwort ist falsch.")

    if user.language is None:
        detected_language = request_ui_language(
            payload.language,
            request.headers.get("accept-language"),
        )
        await db.execute(
            update(User)
            .where(User.id == user.id, User.language.is_(None))
            .values(language=detected_language)
            .execution_options(synchronize_session=False)
        )
        await db.refresh(user)

    raw_session = request.cookies.get(session_cookie_name(settings))
    if raw_session:
        await db.execute(delete(Session).where(Session.token_hash == hash_token(raw_session)))
    await db.execute(
        delete(Session).where(
            Session.user_id == user.id,
            Session.expires_at <= datetime.now(UTC),
        )
    )
    retained = list(
        (
            await db.scalars(
                select(Session.id)
                .where(Session.user_id == user.id)
                .order_by(Session.created_at.desc())
                .offset(9)
            )
        ).all()
    )
    if retained:
        await db.execute(delete(Session).where(Session.id.in_(retained)))
    raw_token, csrf_token = await create_session(db, user, settings, csrf_token)
    await db.commit()
    set_session_cookie(response, settings, raw_token)
    set_csrf_cookie(response, settings, csrf_token)
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth: CurrentAuthWithCsrf,
    db: Database,
    settings: SettingsDependency,
) -> None:
    await db.execute(delete(Session).where(Session.id == auth.session.id))
    await db.commit()
    clear_auth_cookies(response, settings)
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/me", response_model=UserPublic)
async def me(auth: CurrentAuth, response: Response) -> User:
    response.headers["Cache-Control"] = "private, no-store"
    return auth.user
