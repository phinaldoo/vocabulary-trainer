import random
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import Card, Deck, Section, UserCardProgress
from app.schemas import StudySessionCreate
from app.services.study import adaptive_weight, random_selection


def test_random_and_adaptive_probabilities(monkeypatch):
    rng = random.Random(724)
    monkeypatch.setattr("app.services.study.random", rng)
    cards = [Card(id=uuid.uuid4()) for _ in range(3)]
    progress = {
        (cards[0].id, "forward"): UserCardProgress(last_rating=0, repetitions=0, version=2),
        (cards[1].id, "forward"): UserCardProgress(last_rating=3, repetitions=15, version=16),
    }
    assert adaptive_weight(progress[(cards[0].id, "forward")]) > adaptive_weight(None)
    assert adaptive_weight(None) > adaptive_weight(progress[(cards[1].id, "forward")]) > 0
    for mode in ["random", "adaptive"]:
        payload = StudySessionCreate(
            deck_id=uuid.uuid4(),
            direction="forward",
            input_mode="typing",
            selection_mode=mode,
            limit=1,
        )
        counts = Counter(random_selection(cards, progress, payload)[0][0].id for _ in range(6000))
        if mode == "random":
            assert all(1800 < counts[card.id] < 2200 for card in cards)
        else:
            assert counts[cards[0].id] > counts[cards[2].id] > counts[cards[1].id] * 5
            assert counts[cards[1].id] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["random", "adaptive"])
async def test_random_session_scope_resume_and_review(mode):
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        user = await _register(client, "random@example.com")
        async with app.state.session_factory() as db:
            deck = Deck(
                slug="random",
                title="Random",
                front_label="Front",
                back_label="Back",
                front_language="en",
                back_language="de",
                status="published",
                sort_order=1,
            )
            db.add(deck)
            await db.flush()
            sections = [
                Section(deck_id=deck.id, stable_key=str(i), title=f"Chapter {i}", sort_order=i)
                for i in range(2)
            ]
            db.add_all(sections)
            await db.flush()
            cards = [
                Card(
                    deck_id=deck.id,
                    section_id=sections[i % 2].id,
                    stable_key=str(i),
                    sort_order=i,
                    front_text=f"word {i}",
                    back_text=f"answer {i}",
                    active=i < 4,
                )
                for i in range(5)
            ]
            db.add_all(cards)
            await db.flush()
            # All cards are already learned and not due, in both directions.
            for card in cards:
                for direction in ["forward", "reverse"]:
                    db.add(
                        UserCardProgress(
                            user_id=uuid.UUID(user["id"]),
                            card_id=card.id,
                            direction=direction,
                            repetitions=5,
                            last_rating=3,
                            version=5,
                            due_at=datetime.now(UTC) + timedelta(days=30),
                        )
                    )
            await db.commit()
            deck_id, section_id = str(deck.id), str(sections[0].id)
            expected_ids = {str(card.id) for card in cards[:4]}

        config = dict(
            deck_id=deck_id,
            direction="mixed",
            input_mode="reveal",
            selection_mode=mode,
            limit=50,
        )
        response = await client.post(
            "/api/v1/study-sessions", headers=_mutation_headers(client), json=config
        )
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["selection_mode"] == mode
        assert session["total"] == 4
        assert {card["card_id"] for card in session["cards"]} == expected_ids
        assert len({card["section_id"] for card in session["cards"]}) == 2
        assert all(card["state_version"] == 5 and not card["is_new"] for card in session["cards"])
        resumed = await client.get(f"/api/v1/study-sessions/{session['id']}")
        assert resumed.json() == session
        card = session["cards"][0]
        prefix = f"/api/v1/study-sessions/{session['id']}"
        reveal = await client.post(
            f"{prefix}/items/{card['item_id']}/reveal", headers=_mutation_headers(client)
        )
        assert reveal.status_code == 200
        review = await client.post(
            f"{prefix}/reviews",
            headers=_mutation_headers(client),
            json={
                "item_id": card["item_id"],
                "base_version": 5,
                "idempotency_key": str(uuid.uuid4()),
                "response_ms": 1000,
                "response": {"type": "self_assessment", "known": False},
            },
        )
        assert review.status_code == 200, review.text
        assert review.json()["version"] == 6
        scoped = await client.post(
            "/api/v1/study-sessions",
            headers=_mutation_headers(client),
            json={**config, "section_id": section_id, "limit": 1},
        )
        assert scoped.status_code == 200
        assert scoped.json()["total"] == 1
        assert scoped.json()["cards"][0]["section_id"] == section_id
        invalid = await client.post(
            "/api/v1/study-sessions",
            headers=_mutation_headers(client),
            json={**config, "selection_mode": "invalid"},
        )
        assert invalid.status_code == 422
