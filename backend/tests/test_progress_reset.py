import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from sqlalchemy import func, select
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import (
    Card,
    ReviewEvent,
    StudySession,
    UserCardPreference,
    UserCardProgress,
    UserFavorite,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["deck", "all"])
async def test_reset_clears_only_owned_learning_data_and_invalidates_old_sessions(scope):
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other,
    ):
        user = await _register(client, "reset@example.com")
        other_user = await _register(other, "unaffected@example.com")
        decks = [(await make_deck(app, slug=slug))[0] for slug in ["first", "second"]]
        sessions = []
        old_payload = None
        for actor in [client, other]:
            headers = _mutation_headers(actor)
            for deck in decks:
                session = (
                    await actor.post(
                        "/api/v1/study-sessions",
                        headers=headers,
                        json={
                            "deck_id": str(deck.id),
                            "direction": "forward",
                            "input_mode": "typing",
                            "selection_mode": "random",
                            "limit": 2,
                        },
                    )
                ).json()
                item = session["cards"][0]
                path = f"/api/v1/study-sessions/{session['id']}"
                await actor.post(
                    f"{path}/check",
                    headers=headers,
                    json={"item_id": item["item_id"], "answer": "alternative"},
                )
                payload = {
                    "idempotency_key": str(uuid.uuid4()),
                    "item_id": item["item_id"],
                    "base_version": item["state_version"],
                    "response": {
                        "type": "typing",
                        "answer": "alternative",
                        "rating": 2,
                        "accept_as_correct": True,
                    },
                }
                reviewed = await actor.post(f"{path}/reviews", headers=headers, json=payload)
                assert reviewed.status_code == 200, reviewed.text
                await actor.put(f"/api/v1/favorites/{item['card_id']}", headers=headers)
                await actor.put(
                    f"/api/v1/cards/{item['card_id']}/difficulty",
                    headers=headers,
                    json={"difficulty": "hard"},
                )
                if actor is client:
                    sessions.append(session)
                    if old_payload is None:
                        old_payload = payload
        before = (await client.get("/api/v1/auth/me")).json()
        headers = _mutation_headers(client)
        request = {
            "password": "sehr-sicher-123",
            "confirm": True,
            "deck_id": str(decks[0].id) if scope == "deck" else None,
        }
        reset = await client.post("/api/v1/account/progress/reset", headers=headers, json=request)
        assert reset.status_code == 204, reset.text
        assert (await client.get("/api/v1/auth/me")).json() == before
        assert (await client.get(f"/api/v1/study-sessions/{sessions[0]['id']}")).status_code == 404
        replay = await client.post(
            f"/api/v1/study-sessions/{sessions[0]['id']}/reviews", headers=headers, json=old_payload
        )
        assert replay.status_code == 404
        second = await client.get(f"/api/v1/study-sessions/{sessions[1]['id']}")
        assert second.status_code == (200 if scope == "deck" else 404)
        async with app.state.session_factory() as db:
            for model in [UserCardProgress, StudySession, ReviewEvent, UserCardPreference]:
                count = await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.user_id == uuid.UUID(user["id"]))
                )
                assert count == (1 if scope == "deck" else 0), model
                other_count = await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.user_id == uuid.UUID(other_user["id"]))
                )
                assert other_count == 2, model
            assert await db.scalar(select(func.count()).select_from(Card)) == 12
            assert await db.scalar(select(func.count()).select_from(UserFavorite)) == 4
        progress = (await client.get(f"/api/v1/progress?deck_id={decks[0].id}")).json()
        assert progress["reviews"] == 0 and progress["learned"] == 0
        again = await client.post("/api/v1/account/progress/reset", headers=headers, json=request)
        assert again.status_code == 204
        fresh = (
            await client.post(
                "/api/v1/study-sessions",
                headers=headers,
                json={
                    "deck_id": str(decks[0].id),
                    "direction": "forward",
                    "input_mode": "typing",
                    "limit": 2,
                },
            )
        ).json()
        assert all(item["state_version"] == 0 and item["is_new"] for item in fresh["cards"])


@pytest.mark.asyncio
async def test_reset_requires_password_confirmation_and_valid_scope():
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "reset-validation@example.com")
        deck, _, cards = await make_deck(app)
        headers = _mutation_headers(client)
        await client.put(
            f"/api/v1/cards/{cards[0].id}/difficulty", headers=headers, json={"difficulty": "hard"}
        )
        endpoint = "/api/v1/account/progress/reset"
        base = {"password": "sehr-sicher-123", "confirm": True, "deck_id": str(deck.id)}
        assert (await client.post(endpoint, json=base)).status_code == 403
        for overrides, code in [
            ({"password": "wrong"}, 403),
            ({"confirm": False}, 422),
            ({"deck_id": str(uuid.uuid4())}, 404),
        ]:
            result = await client.post(endpoint, headers=headers, json={**base, **overrides})
            assert result.status_code == code, result.text
        missing = await client.post(endpoint, headers=headers, json={"password": base["password"]})
        assert missing.status_code == 422
        async with app.state.session_factory() as db:
            assert await db.scalar(select(func.count()).select_from(UserCardPreference)) == 1
