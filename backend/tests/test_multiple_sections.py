import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import Card, Deck, Section


@pytest.mark.parametrize("mode", ["scheduled", "random", "adaptive"])
async def test_multiple_sections_scope_validation_and_persistence(mode):
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "multiple@example.com")
        async with app.state.session_factory() as db:
            decks = [
                Deck(
                    slug=f"deck-{i}",
                    title=f"Deck {i}",
                    front_label="Front",
                    back_label="Back",
                    front_language="en",
                    back_language="de",
                    status="published",
                    sort_order=i,
                )
                for i in range(2)
            ]
            db.add_all(decks)
            await db.flush()
            sections = [
                Section(
                    deck_id=decks[0 if i < 4 else 1].id,
                    stable_key=str(i),
                    title=f"Chapter {i}",
                    sort_order=i,
                    active=i != 3,
                )
                for i in range(5)
            ]
            db.add_all(sections)
            await db.flush()
            for i, section in enumerate(sections):
                db.add(
                    Card(
                        deck_id=section.deck_id,
                        section_id=section.id,
                        stable_key=str(i),
                        sort_order=i,
                        front_text=f"word {i}",
                        back_text=f"answer {i}",
                    )
                )
            db.add(
                Card(
                    deck_id=decks[0].id,
                    stable_key="unsectioned",
                    sort_order=9,
                    front_text="other",
                    back_text="other",
                )
            )
            db.add(
                Card(
                    deck_id=decks[0].id,
                    section_id=sections[0].id,
                    stable_key="inactive",
                    sort_order=10,
                    front_text="old",
                    back_text="old",
                    active=False,
                )
            )
            await db.commit()
            deck_id = str(decks[0].id)
            ids = [str(section.id) for section in sections]
        config = dict(
            deck_id=deck_id, direction="mixed", input_mode="reveal", selection_mode=mode, limit=50
        )
        chosen = ids[:2]
        response = await client.post(
            "/api/v1/study-sessions",
            headers=_mutation_headers(client),
            json={**config, "section_ids": [*chosen, chosen[0]]},
        )
        assert response.status_code == 200, response.text
        session = response.json()
        assert session["section_ids"] == chosen
        assert session["section_titles"] == ["Chapter 0", "Chapter 1"]
        assert session["section_id"] is None
        assert session["total"] == 2
        assert {card["section_id"] for card in session["cards"]} == set(chosen)
        resumed = await client.get(f"/api/v1/study-sessions/{session['id']}")
        assert resumed.json() == session
        account = (await client.get("/api/v1/auth/me")).json()
        assert account["selected_section_ids"] == chosen

        for invalid in [ids[3], ids[4], str(uuid.uuid4())]:
            bad = await client.post(
                "/api/v1/study-sessions",
                headers=_mutation_headers(client),
                json={**config, "section_ids": [ids[0], invalid]},
            )
            assert bad.status_code == 404
        bad = await client.post(
            "/api/v1/study-sessions",
            headers=_mutation_headers(client),
            json={**config, "section_id": ids[2], "section_ids": chosen},
        )
        assert bad.status_code == 422
        settings = dict(
            daily_goal=20,
            direction="forward",
            input_mode="typing",
            selected_deck_id=deck_id,
            selected_section_id=None,
        )
        saved = await client.patch(
            "/api/v1/account/settings", headers=_mutation_headers(client), json=settings
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["selected_section_ids"] == chosen
        reset = await client.patch(
            "/api/v1/account/settings",
            headers=_mutation_headers(client),
            json={**settings, "selected_section_ids": []},
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["selected_section_ids"] == []
        single = await client.post(
            "/api/v1/study-sessions",
            headers=_mutation_headers(client),
            json={**config, "section_id": ids[0]},
        )
        assert single.json()["section_ids"] == [ids[0]]
        assert single.json()["section_id"] == ids[0]
        all_sections = await client.post(
            "/api/v1/study-sessions",
            headers=_mutation_headers(client),
            json={**config, "section_ids": []},
        )
        assert all_sections.json()["section_ids"] == []
        assert all_sections.json()["total"] > 2
