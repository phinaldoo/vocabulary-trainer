from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import Settings


def create_database(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL could not be configured")
    options: dict[str, object] = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite+aiosqlite:///:memory:"):
        options["poolclass"] = StaticPool
        options["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(settings.database_url, **options)
    if settings.database_url.startswith("sqlite+aiosqlite:"):

        @event.listens_for(engine.sync_engine, "connect")
        def enable_sqlite_foreign_keys(connection, _) -> None:  # type: ignore[no-untyped-def]
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session
