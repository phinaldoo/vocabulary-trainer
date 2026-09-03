from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import account, admin, auth, catalog, progress, study
from app.config import Settings, get_settings
from app.database import create_database
from app.errors import ApiError, api_error_handler
from app.models import Base, Card, Deck


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    engine, session_factory = create_database(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if config.auto_create_schema:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    app = FastAPI(
        title=config.app_name,
        version="2.0.0",
        docs_url="/api/docs" if config.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if config.environment != "production" else None,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.add_middleware(GZipMiddleware, minimum_size=1_000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)

    auth_attempts: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def request_guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        try:
            content_length = int(request.headers.get("content-length") or 0)
        except ValueError:
            content_length = 65_537
        request_limit = (
            config.max_import_bytes
            if request.url.path == f"{config.api_prefix}/admin/import"
            else config.max_request_bytes
        )
        if content_length > request_limit:
            response = JSONResponse(
                status_code=413,
                content={
                    "error": {"code": "payload_too_large", "message": "Die Anfrage ist zu groß."},
                    "request_id": request_id,
                },
            )
        else:
            if request.url.path in {
                f"{config.api_prefix}/auth/login",
                f"{config.api_prefix}/auth/register",
            }:
                host = request.headers.get("x-real-ip") or (
                    request.client.host if request.client else "unknown"
                )
                key = f"{host}:{request.url.path}"
                now = time.monotonic()
                attempts = auth_attempts[key]
                while attempts and attempts[0] < now - 60:
                    attempts.popleft()
                if len(auth_attempts) > 4_096:
                    stale_keys = [
                        candidate
                        for candidate, values in auth_attempts.items()
                        if not values or values[-1] < now - 60
                    ]
                    for stale_key in stale_keys:
                        auth_attempts.pop(stale_key, None)
                    while len(auth_attempts) > 4_096:
                        auth_attempts.pop(next(iter(auth_attempts)))
                if len(attempts) >= 12:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "rate_limited",
                                "message": "Zu viele Versuche. Bitte warte einen Moment.",
                            },
                            "request_id": request_id,
                        },
                        headers={"Retry-After": "60", "Cache-Control": "private, no-store"},
                    )
                attempts.append(now)
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        if request.url.path.startswith(config.api_prefix):
            response.headers.setdefault("Cache-Control", "private, no-store")
        return response

    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Bitte prüfe deine Eingaben.",
                },
                "request_id": getattr(request.state, "request_id", None),
            },
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def ready() -> JSONResponse:
        try:
            async with session_factory() as db:
                await db.execute(text("SELECT 1"))
                decks = int(
                    await db.scalar(
                        select(func.count()).select_from(Deck).where(Deck.status == "published")
                    )
                    or 0
                )
                cards = int(
                    await db.scalar(
                        select(func.count())
                        .select_from(Card)
                        .join(Deck, Deck.id == Card.deck_id)
                        .where(Card.active.is_(True), Deck.status == "published")
                    )
                    or 0
                )
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse(content={"status": "ready", "decks": decks, "cards": cards})

    for router in (
        auth.router,
        account.router,
        catalog.router,
        study.router,
        progress.router,
        admin.router,
    ):
        app.include_router(router, prefix=config.api_prefix)

    return app


app = create_app()
