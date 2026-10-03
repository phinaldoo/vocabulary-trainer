import random

import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from sqlalchemy import select
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import Card, Section


@pytest.mark.asyncio
async def test_random_samples_all_97_chapters_and_persists_the_selection(monkeypatch):
    monkeypatch.setattr("app.services.study.random", random.Random(9731))
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "random-preference@example.com")
        deck, sections, _ = await make_deck(app, count=97)
        async with app.state.session_factory() as db:
            extra = [
                Section(deck_id=deck.id, stable_key=str(i), title=f"Chapter {i}", sort_order=i)
                for i in range(4, 98)
            ]
            db.add_all(extra)
            await db.flush()
            all_sections = [*sections, *extra]
            cards = list(await db.scalars(select(Card).order_by(Card.sort_order)))
            for card, section in zip(cards, all_sections, strict=True):
                card.section_id = section.id
            await db.commit()
        headers = _mutation_headers(client)
        started = await client.post(
            "/api/v1/study-sessions",
            headers=headers,
            json={
                "deck_id": str(deck.id),
                "input_mode": "typing",
                "direction": "mixed",
                "selection_mode": "random",
                "section_ids": [],
                "limit": 50,
            },
        )
        assert started.status_code == 200, started.text
        session = started.json()
        order = {str(card.id): card.sort_order for card in cards}
        selected = [order[item["card_id"]] for item in session["cards"]]
        assert len(set(selected)) == 50
        assert max(selected) > 90 and min(selected) < 10
        assert selected != sorted(selected)
        resumed = (await client.get(f"/api/v1/study-sessions/{session['id']}")).json()
        assert resumed["cards"] == session["cards"]
        assert (await client.get("/api/v1/auth/me")).json()["selection_mode"] == "random"
        settings = {"daily_goal": 12, "input_mode": "typing", "direction": "forward"}
        legacy_update = await client.patch(
            "/api/v1/account/settings", headers=headers, json=settings
        )
        assert legacy_update.status_code == 200, legacy_update.text
        assert legacy_update.json()["selection_mode"] == "random"
        saved = await client.patch(
            "/api/v1/account/settings",
            headers=headers,
            json={**settings, "selection_mode": "adaptive"},
        )
        assert saved.json()["selection_mode"] == "adaptive"
        assert (await client.get("/api/v1/auth/me")).json()["selection_mode"] == "adaptive"
