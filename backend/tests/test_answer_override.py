import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from sqlalchemy import select
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import ReviewEvent, UserCardProgress


@pytest.mark.asyncio
@pytest.mark.parametrize("accept", [False, True])
async def test_override_requires_checked_answer_and_updates_progress_once(accept):
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "override@example.com")
        deck, _, cards = await make_deck(app, count=1)
        headers = _mutation_headers(client)
        session = (
            await client.post(
                "/api/v1/study-sessions",
                headers=headers,
                json={
                    "deck_id": str(deck.id),
                    "input_mode": "typing",
                    "direction": "forward",
                    "limit": 1,
                },
            )
        ).json()
        item = session["cards"][0]
        path = f"/api/v1/study-sessions/{session['id']}"
        payload = {
            "idempotency_key": str(uuid.uuid4()),
            "item_id": item["item_id"],
            "base_version": item["state_version"],
            "response": {
                "type": "typing",
                "answer": "valid alternative",
                "rating": 2,
                "accept_as_correct": accept,
            },
        }
        premature = await client.post(f"{path}/reviews", headers=headers, json=payload)
        assert premature.status_code == 409
        assert premature.json()["error"]["code"] == "answer_not_checked"
        checked = await client.post(
            f"{path}/check",
            headers=headers,
            json={
                "item_id": item["item_id"],
                "answer": "valid alternative",
            },
        )
        assert checked.json()["correct"] is False
        changed = {**payload, "response": {**payload["response"], "answer": "different"}}
        assert (
            await client.post(f"{path}/reviews", headers=headers, json=changed)
        ).status_code == 409
        response = await client.post(f"{path}/reviews", headers=headers, json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["correct"] is accept
        assert result["correct_reviewed"] == int(accept)
        assert result["effective_rating"] == (2 if accept else 0)
        assert result["match_kind"] == ("manual_override" if accept else None)
        assert (
            await client.post(f"{path}/reviews", headers=headers, json=payload)
        ).json() == result
        resumed = (await client.get(path)).json()
        assert resumed["correct_reviewed"] == int(accept)
        async with app.state.session_factory() as db:
            progress = await db.scalar(select(UserCardProgress))
            assert progress.version == 1
            assert progress.last_rating == (2 if accept else 0)
            events = list(await db.scalars(select(ReviewEvent)))
            assert len(events) == 1
            assert events[0].was_correct is accept
            assert events[0].answer == "valid alternative"
            assert (await db.get(type(cards[0]), cards[0].id)).back_answers == []
