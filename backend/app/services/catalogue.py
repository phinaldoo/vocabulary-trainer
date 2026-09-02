from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Card, Deck, DeckVersion, Section
from app.schemas import DeckManifest, DeckPublic, ImportResult
from app.services.answer_matcher import validate_answer_spec

DECK_NAMESPACE = uuid.UUID("f1542a2f-878a-48b7-b269-ad9b7be581b3")


def deck_id_for_slug(slug: str) -> uuid.UUID:
    return uuid.uuid5(DECK_NAMESPACE, slug)


def section_id_for_key(deck_id: uuid.UUID, key: str) -> uuid.UUID:
    return uuid.uuid5(deck_id, f"section:{key}")


def card_id_for_key(deck_id: uuid.UUID, key: str) -> uuid.UUID:
    return uuid.uuid5(deck_id, f"card:{key}")


def manifest_digest(manifest: DeckManifest) -> str:
    encoded = json.dumps(
        manifest.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def deck_public(db: AsyncSession, deck: Deck) -> DeckPublic:
    section_count = int(
        await db.scalar(
            select(func.count())
            .select_from(Section)
            .where(Section.deck_id == deck.id, Section.active.is_(True))
        )
        or 0
    )
    card_count = int(
        await db.scalar(
            select(func.count())
            .select_from(Card)
            .where(Card.deck_id == deck.id, Card.active.is_(True))
        )
        or 0
    )
    return DeckPublic.model_validate(deck).model_copy(
        update={"section_count": section_count, "card_count": card_count}
    )


async def published_decks(db: AsyncSession) -> list[Deck]:
    return list(
        (
            await db.scalars(
                select(Deck).where(Deck.status == "published").order_by(Deck.sort_order, Deck.title)
            )
        ).all()
    )


async def resolve_published_deck(
    db: AsyncSession, selected_deck_id: uuid.UUID | None
) -> Deck | None:
    if selected_deck_id:
        selected = await db.scalar(
            select(Deck).where(Deck.id == selected_deck_id, Deck.status == "published")
        )
        if selected:
            return selected
    return await db.scalar(
        select(Deck).where(Deck.status == "published").order_by(Deck.sort_order).limit(1)
    )


def validate_manifest_answers(manifest: DeckManifest) -> None:
    for card in manifest.cards:
        validate_answer_spec(
            card.front.text,
            card.front.answers,
            matcher_profile=manifest.front.matcher,
        )
        validate_answer_spec(
            card.back.text,
            card.back.answers,
            matcher_profile=manifest.back.matcher,
        )


async def import_manifest(
    db: AsyncSession,
    manifest: DeckManifest,
    *,
    publish_new: bool = False,
) -> ImportResult:
    """Validate and atomically upsert one installation-wide shared deck."""

    try:
        validate_manifest_answers(manifest)
    except ValueError as exc:
        raise ApiError(422, "invalid_answer_spec", str(exc)) from exc

    digest = manifest_digest(manifest)
    deck = await db.scalar(select(Deck).where(Deck.slug == manifest.id).with_for_update())
    if deck and deck.content_hash == digest:
        return ImportResult(deck=await deck_public(db, deck), unchanged=True)
    if deck and manifest.version < deck.version:
        raise ApiError(
            409,
            "deck_version_older",
            f"Version {deck.version} ist bereits installiert.",
        )
    if deck and manifest.version == deck.version and deck.content_hash:
        raise ApiError(
            409,
            "deck_version_conflict",
            "Dieselbe Deck-Version enthält andere Daten. Erhöhe zuerst die Version.",
        )

    if deck is None:
        next_order = int(await db.scalar(select(func.max(Deck.sort_order))) or 0) + 1
        deck = Deck(
            id=deck_id_for_slug(manifest.id),
            slug=manifest.id,
            title=manifest.title,
            front_label=manifest.front.label,
            back_label=manifest.back.label,
            front_language=manifest.front.language,
            back_language=manifest.back.language,
            status="published" if publish_new else "draft",
            version=manifest.version,
            sort_order=next_order,
        )
        db.add(deck)
        await db.flush()

    deck.title = manifest.title
    deck.description = manifest.description
    deck.front_label = manifest.front.label
    deck.back_label = manifest.back.label
    deck.front_language = manifest.front.language
    deck.back_language = manifest.back.language
    deck.front_matcher = manifest.front.matcher
    deck.back_matcher = manifest.back.matcher
    deck.version = manifest.version
    deck.license = manifest.license
    deck.attribution = manifest.attribution
    deck.content_hash = digest

    existing_sections = list(
        (await db.scalars(select(Section).where(Section.deck_id == deck.id))).all()
    )
    sections_by_key = {section.stable_key: section for section in existing_sections}
    for index, section in enumerate(existing_sections, start=1):
        section.sort_order = -index
    await db.flush()

    created_sections = 0
    updated_sections = 0
    imported_sections: set[str] = set()
    for entry in manifest.sections:
        imported_sections.add(entry.id)
        section = sections_by_key.get(entry.id)
        if section is None:
            section = Section(
                id=section_id_for_key(deck.id, entry.id),
                deck_id=deck.id,
                stable_key=entry.id,
                title=entry.title,
                sort_order=entry.order,
                active=True,
            )
            db.add(section)
            sections_by_key[entry.id] = section
            created_sections += 1
        else:
            section.title = entry.title
            section.sort_order = entry.order
            section.active = True
            updated_sections += 1
    for key, section in sections_by_key.items():
        if key not in imported_sections:
            section.active = False
    await db.flush()

    existing_cards = list((await db.scalars(select(Card).where(Card.deck_id == deck.id))).all())
    cards_by_key = {card.stable_key: card for card in existing_cards}
    for index, card in enumerate(existing_cards, start=1):
        card.sort_order = -index
    await db.flush()

    created_cards = 0
    updated_cards = 0
    imported_cards: set[str] = set()
    for entry in manifest.cards:
        imported_cards.add(entry.id)
        section_id = sections_by_key[entry.section].id if entry.section else None
        card = cards_by_key.get(entry.id)
        if card is None:
            card = Card(
                id=card_id_for_key(deck.id, entry.id),
                deck_id=deck.id,
                stable_key=entry.id,
                section_id=section_id,
                sort_order=entry.order,
                front_text=entry.front.text,
                back_text=entry.back.text,
                front_answers=entry.front.answers,
                back_answers=entry.back.answers,
                details=entry.metadata,
                active=True,
                content_version=manifest.version,
            )
            db.add(card)
            cards_by_key[entry.id] = card
            created_cards += 1
        else:
            card.section_id = section_id
            card.sort_order = entry.order
            card.front_text = entry.front.text
            card.back_text = entry.back.text
            card.front_answers = entry.front.answers
            card.back_answers = entry.back.answers
            card.details = entry.metadata
            card.active = True
            card.content_version = manifest.version
            updated_cards += 1

    archived_cards = 0
    for key, card in cards_by_key.items():
        if key not in imported_cards and card.active:
            card.active = False
            archived_cards += 1

    previous = await db.scalar(
        select(DeckVersion).where(DeckVersion.deck_id == deck.id, DeckVersion.sha256 == digest)
    )
    if previous is None:
        db.add(
            DeckVersion(
                deck_id=deck.id,
                version=manifest.version,
                sha256=digest,
                item_count=len(manifest.cards),
                warnings=[],
                manifest=manifest.model_dump(mode="json", by_alias=True),
            )
        )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(deck)
    return ImportResult(
        deck=await deck_public(db, deck),
        created_sections=created_sections,
        updated_sections=updated_sections,
        created_cards=created_cards,
        updated_cards=updated_cards,
        archived_cards=archived_cards,
    )
