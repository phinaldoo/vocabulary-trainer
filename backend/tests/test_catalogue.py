import json
from pathlib import Path

from app.schemas import DeckManifest
from app.services.catalogue import (
    card_id_for_key,
    deck_id_for_slug,
    manifest_digest,
    section_id_for_key,
    validate_manifest_answers,
)


def test_generic_manifest_has_stable_identifiers_and_digest() -> None:
    manifest = DeckManifest.model_validate(
        {
            "schemaVersion": 1,
            "id": "synthetic-test",
            "version": 1,
            "title": "Synthetic test deck",
            "front": {"label": "Prompt", "language": "zxx", "matcher": "generic-v1"},
            "back": {"label": "Answer", "language": "zxx", "matcher": "generic-v1"},
            "sections": [{"id": "generated", "title": "Generated samples", "order": 1}],
            "cards": [
                {
                    "id": "nuvexa-47",
                    "section": "generated",
                    "order": 1,
                    "front": {"text": "nuvexa-47", "answers": []},
                    "back": {"text": "qarilo-82", "answers": []},
                    "metadata": {"kind": "synthetic"},
                }
            ],
        }
    )
    deck_id = deck_id_for_slug(manifest.id)
    section_ids = [section_id_for_key(deck_id, section.id) for section in manifest.sections]
    card_ids = [card_id_for_key(deck_id, card.id) for card in manifest.cards]

    assert manifest.schema_version == 1
    assert manifest.cards
    assert len(section_ids) == len(set(section_ids))
    assert len(card_ids) == len(set(card_ids))
    assert len(manifest_digest(manifest)) == 64


def test_published_example_manifest_is_valid() -> None:
    container_path = Path.cwd() / "examples" / "synthetic-demo.json"
    repository_path = Path(__file__).resolve().parents[2] / "examples" / "synthetic-demo.json"
    path = container_path if container_path.exists() else repository_path

    manifest = DeckManifest.model_validate(json.loads(path.read_text("utf-8")))
    validate_manifest_answers(manifest)

    assert manifest.id == "synthetic-demo"
    assert manifest.license is None
    assert manifest.attribution is None
    assert len(manifest.cards) == 2
