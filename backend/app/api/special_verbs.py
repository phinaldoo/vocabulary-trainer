from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentAdminWithCsrf, Database
from app.errors import ApiError
from app.models import Deck
from app.schemas import ImportResult
from app.services.catalogue import deck_public, import_manifest
from app.services.special_verbs import (
    VerbCsvPreview,
    VerbCsvRequest,
    preview_verb_csv,
    verb_manifest,
)

router = APIRouter(prefix="/admin/special-verbs", tags=["special-verbs"])


@router.post("/preview", response_model=VerbCsvPreview)
async def preview(payload: VerbCsvRequest, auth: CurrentAdminWithCsrf) -> VerbCsvPreview:
    del auth
    return preview_verb_csv(payload)


@router.post("/import", response_model=ImportResult)
async def import_csv(
    payload: VerbCsvRequest, auth: CurrentAdminWithCsrf, db: Database,
) -> ImportResult:
    del auth
    parsed = preview_verb_csv(payload)
    if parsed.errors:
        raise ApiError(422, "invalid_verb_csv", "Please fix the CSV errors shown in the preview.")
    manifest = verb_manifest(payload.title, parsed.rows)
    existing = await db.scalar(select(Deck).where(Deck.slug == manifest.id))
    if existing:
        # Do not reset progress, overwrite later edits, or republish archived content.
        return ImportResult(deck=await deck_public(db, existing), unchanged=True)
    try:
        return await import_manifest(db, manifest, publish_new=True)
    except IntegrityError as exc:
        await db.rollback()
        existing = await db.scalar(select(Deck).where(Deck.slug == manifest.id))
        if existing:
            return ImportResult(deck=await deck_public(db, existing), unchanged=True)
        raise ApiError(409, "deck_conflict", "Please retry the import.") from exc
