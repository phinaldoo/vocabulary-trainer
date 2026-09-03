from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import Session, User

password_hash = PasswordHash.recommended()


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    session: Session


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hash.verify(password, encoded)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_cookie_name(settings: Settings) -> str:
    if settings.cookie_secure and not settings.cookie_domain:
        return "__Host-vocabulary_trainer_session"
    return "vocabulary_trainer_session"


def csrf_cookie_name(settings: Settings) -> str:
    return "vocabulary_trainer_csrf"


def set_csrf_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        csrf_cookie_name(settings),
        token,
        max_age=settings.session_days * 86_400,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        session_cookie_name(settings),
        token,
        max_age=settings.session_days * 86_400,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name in (session_cookie_name(settings), csrf_cookie_name(settings)):
        response.delete_cookie(
            name,
            path="/",
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=name == session_cookie_name(settings),
            samesite="lax",
        )


def verify_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    if origin.rstrip("/") not in {item.rstrip("/") for item in settings.allowed_origins}:
        raise ApiError(403, "origin_not_allowed", "Diese Anfrage wurde abgelehnt.")


def verify_same_site_request(request: Request, settings: Settings) -> None:
    verify_origin(request, settings)
    if request.headers.get("sec-fetch-site", "").casefold() == "cross-site":
        raise ApiError(403, "cross_site_request", "Diese Anfrage wurde abgelehnt.")


def verify_double_submit_csrf(request: Request, settings: Settings) -> str:
    verify_same_site_request(request, settings)
    cookie = request.cookies.get(csrf_cookie_name(settings), "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise ApiError(403, "csrf_invalid", "Die Sicherheitsprüfung ist fehlgeschlagen.")
    return header


async def create_session(
    db: AsyncSession,
    user: User,
    settings: Settings,
    csrf_token: str | None = None,
) -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(48)
    csrf_token = csrf_token or secrets.token_urlsafe(32)
    session = Session(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_hash=hash_token(csrf_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.session_days),
    )
    db.add(session)
    await db.flush()
    return raw_token, csrf_token


async def authenticate_request(
    request: Request,
    db: AsyncSession,
    settings: Settings,
) -> AuthenticatedUser:
    raw_token = request.cookies.get(session_cookie_name(settings))
    if not raw_token:
        raise ApiError(401, "unauthorized", "Bitte melde dich an.")

    row = (
        await db.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(Session.token_hash == hash_token(raw_token))
        )
    ).first()
    if not row:
        raise ApiError(401, "unauthorized", "Bitte melde dich erneut an.")

    session, user = row
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        await db.execute(delete(Session).where(Session.id == session.id))
        await db.commit()
        raise ApiError(401, "session_expired", "Deine Sitzung ist abgelaufen.")
    now = datetime.now(UTC)
    last_seen_at = session.last_seen_at
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    if last_seen_at <= now - timedelta(minutes=5):
        session.last_seen_at = now
        await db.commit()
    return AuthenticatedUser(user=user, session=session)


def verify_session_csrf(
    request: Request,
    settings: Settings,
    auth: AuthenticatedUser,
) -> None:
    token = verify_double_submit_csrf(request, settings)
    if not hmac.compare_digest(hash_token(token), auth.session.csrf_hash):
        raise ApiError(403, "csrf_invalid", "Die Sicherheitsprüfung ist fehlgeschlagen.")
