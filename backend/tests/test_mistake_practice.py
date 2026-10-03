import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import UserCardProgress


@pytest.mark.asyncio
async def test_failed_answer_returns_immediately_then_leaves_after_manual_correction():
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "mistakes@example.com")
        deck, _, _ = await make_deck(app)
        headers = _mutation_headers(client)

        async def start(mode, limit=3):
            response = await client.post(
                "/api/v1/study-sessions",
                headers=headers,
                json={
                    "deck_id": str(deck.id),
                    "input_mode": "typing",
                    "direction": "forward",
                    "selection_mode": mode,
                    "limit": limit,
                },
            )
            assert response.status_code == 200, response.text
            return response.json()

        initial = await start("scheduled", 1)
        item = initial["cards"][0]

        async def answer(session, item, accept=False):
            path = f"/api/v1/study-sessions/{session['id']}"
            check = await client.post(
                f"{path}/check",
                headers=headers,
                json={"item_id": item["item_id"], "answer": "alternative"},
            )
            assert check.json()["correct"] is False
            review = await client.post(
                f"{path}/reviews",
                headers=headers,
                json={
                    "idempotency_key": str(uuid.uuid4()),
                    "item_id": item["item_id"],
                    "base_version": item["state_version"],
                    "response": {
                        "type": "typing",
                        "answer": "alternative",
                        "rating": 2,
                        "accept_as_correct": accept,
                    },
                },
            )
            assert review.status_code == 200, review.text
            return review.json()

        failed = await answer(initial, item)
        assert datetime.fromisoformat(failed["due_at"]) > datetime.now(UTC)
        scheduled = await start("scheduled")
        assert scheduled["cards"][0]["card_id"] == item["card_id"]
        assert len({card["card_id"] for card in scheduled["cards"]}) == 3
        mistakes = await start("mistakes")
        assert mistakes["total"] == 1
        assert mistakes["cards"][0]["card_id"] == item["card_id"]
        corrected = await answer(mistakes, mistakes["cards"][0], accept=True)
        assert corrected["correct"] is True
        empty = await start("mistakes")
        assert empty["total"] == 0 and empty["complete"] is True
        assert empty["cards"] == []


@pytest.mark.asyncio
async def test_mistakes_respect_user_deck_sections_and_direction():
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other,
    ):
        user = await _register(client, "scope@example.com")
        await _register(other, "other@example.com")
        deck, sections, cards = await make_deck(app)
        another, _, _ = await make_deck(app, slug="another")
        async with app.state.session_factory() as db:
            for card, direction in [
                (cards[0], "forward"),
                (cards[0], "reverse"),
                (cards[1], "forward"),
            ]:
                db.add(
                    UserCardProgress(
                        user_id=uuid.UUID(user["id"]),
                        card_id=card.id,
                        direction=direction,
                        last_rating=0,
                        due_at=datetime.now(UTC) + timedelta(minutes=10),
                    )
                )
            await db.commit()
        config = {
            "deck_id": str(deck.id),
            "section_ids": [str(sections[0].id)],
            "input_mode": "typing",
            "direction": "mixed",
            "selection_mode": "mistakes",
            "limit": 50,
        }
        for actor, overrides, expected in [
            (client, {}, 1),
            (other, {}, 0),
            (client, {"deck_id": str(another.id), "section_ids": []}, 0),
            (client, {"section_ids": [str(sections[1].id)], "direction": "reverse"}, 0),
            (client, {"section_ids": [str(sections[1].id)], "direction": "forward"}, 1),
        ]:
            result = await actor.post(
                "/api/v1/study-sessions",
                headers=_mutation_headers(actor),
                json={**config, **overrides},
            )
            assert result.status_code == 200, result.text
            assert result.json()["total"] == expected
            assert len({item["card_id"] for item in result.json()["cards"]}) == expected
