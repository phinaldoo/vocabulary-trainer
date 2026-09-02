from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_db
from app.errors import ApiError
from app.security import AuthenticatedUser, authenticate_request, verify_session_csrf

Database = Annotated[AsyncSession, Depends(get_db)]


def settings_from_request(request: Request) -> Settings:
    return request.app.state.settings


SettingsDependency = Annotated[Settings, Depends(settings_from_request)]


async def current_auth(
    request: Request,
    db: Database,
    settings: SettingsDependency,
) -> AuthenticatedUser:
    return await authenticate_request(request, db, settings)


CurrentAuth = Annotated[AuthenticatedUser, Depends(current_auth)]


async def current_auth_with_csrf(
    request: Request,
    auth: CurrentAuth,
    settings: SettingsDependency,
) -> AuthenticatedUser:
    verify_session_csrf(request, settings, auth)
    return auth


CurrentAuthWithCsrf = Annotated[AuthenticatedUser, Depends(current_auth_with_csrf)]


async def current_admin(auth: CurrentAuth) -> AuthenticatedUser:
    if auth.user.role != "admin":
        raise ApiError(403, "admin_required", "Für diese Aktion werden Adminrechte benötigt.")
    return auth


CurrentAdmin = Annotated[AuthenticatedUser, Depends(current_admin)]


async def current_admin_with_csrf(
    request: Request,
    auth: CurrentAdmin,
    settings: SettingsDependency,
) -> AuthenticatedUser:
    verify_session_csrf(request, settings, auth)
    return auth


CurrentAdminWithCsrf = Annotated[AuthenticatedUser, Depends(current_admin_with_csrf)]
