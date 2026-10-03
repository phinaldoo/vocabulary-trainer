import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app


@pytest.mark.asyncio
async def test_metadata_roundtrip_and_session_snapshot():
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "metadata@example.com")
        deck, _, _ = await make_deck(app, count=0)
        headers = _mutation_headers(client)
        metadata = {
            "gender": "f.",
            "part_of_speech": "noun",
            "additional_info": "First declension",
            "additional_info_2": "An example",
            "custom": {"source": "book"},
        }
        body = {
            "stable_key": "rosa",
            "sort_order": 1,
            "front_text": "rosa",
            "back_text": "Rose",
            "metadata": metadata,
        }
        created = await client.post(
            f"/api/v1/admin/decks/{deck.id}/cards",
            headers=headers,
            json=body,
        )
        assert created.status_code == 201, created.text
        card = created.json()
        catalogue = (await client.get(f"/api/v1/cards?deck_id={deck.id}")).json()
        assert catalogue["items"][0]["metadata"] == metadata
        started = await client.post(
            "/api/v1/study-sessions",
            headers=headers,
            json={
                "deck_id": str(deck.id),
                "direction": "forward",
                "input_mode": "typing",
                "limit": 1,
            },
        )
        session = started.json()
        assert session["cards"][0]["metadata"] == metadata
        updated = await client.patch(
            f"/api/v1/admin/decks/{deck.id}/cards/{card['id']}",
            headers=headers,
            json={
                key: value
                for key, value in {
                    **body,
                    "metadata": {**metadata, "additional_info_2": "Edited"},
                }.items()
                if key != "stable_key"
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["metadata"]["additional_info_2"] == "Edited"
        resumed = (await client.get(f"/api/v1/study-sessions/{session['id']}")).json()
        assert resumed["cards"][0]["metadata"] == metadata
