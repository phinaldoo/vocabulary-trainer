from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import create_database
from app.models import Deck
from app.schemas import DeckManifest
from app.services.catalogue import import_manifest


async def seed_decks(path: Path | None = None) -> None:
    """Install bundled shared decks once; subsequent changes belong to administrators."""

    settings = get_settings()
    source = path or settings.content_data_path
    paths = (
        sorted(source.glob("*.json")) if source.is_dir() else ([source] if source.exists() else [])
    )
    engine, session_factory = create_database(settings)
    try:
        for manifest_path in paths:
            try:
                manifest = DeckManifest.model_validate(json.loads(manifest_path.read_text("utf-8")))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise RuntimeError(f"Invalid deck manifest {manifest_path}: {exc}") from exc
            async with session_factory() as db:
                existing = await db.scalar(select(Deck.id).where(Deck.slug == manifest.id))
                if existing:
                    continue
                await import_manifest(db, manifest, publish_new=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_decks())
