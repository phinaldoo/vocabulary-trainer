"""Run against a dedicated migrated test DB with TEST_POSTGRES_URL set."""

import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from sqlalchemy import delete, select
from test_api_workflows import _mutation_headers, _register, _settings

from app.api import account, study
from app.main import create_app
from app.models import Deck, ReviewEvent, StudySession, User, UserCardProgress
from app.services.study import lock_learning_state


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="Requires PostgreSQL test DB")
async def test_reset_serializes_with_an_in_flight_review(monkeypatch):
    settings = _settings().model_copy(
        update={
            "database_url": os.environ["TEST_POSTGRES_URL"],
            "auto_create_schema": False,
        }
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        key = uuid.uuid4().hex
        user = await _register(client, f"reset-{key}@example.com")
        user_id = uuid.UUID(user["id"])
        deck, _, _ = await make_deck(app, slug=f"reset-{key}", count=1)
        headers = _mutation_headers(client)
        session = (
            await client.post(
                "/api/v1/study-sessions",
                headers=headers,
                json={
                    "deck_id": str(deck.id),
                    "direction": "forward",
                    "input_mode": "typing",
                    "limit": 1,
                },
            )
        ).json()
        item = session["cards"][0]
        await client.post(
            f"/api/v1/study-sessions/{session['id']}/check",
            headers=headers,
            json={"item_id": item["item_id"], "answer": "alternative"},
        )
        reset_locked = asyncio.Event()
        release_reset = asyncio.Event()
        review_waiting = asyncio.Event()

        async def pause_reset(db, uid):
            await lock_learning_state(db, uid)
            reset_locked.set()
            await release_reset.wait()

        async def observe_review(db, uid):
            review_waiting.set()
            await lock_learning_state(db, uid)

        monkeypatch.setattr(account, "lock_learning_state", pause_reset)
        monkeypatch.setattr(study, "lock_learning_state", observe_review)
        reset_task = asyncio.create_task(
            client.post(
                "/api/v1/account/progress/reset",
                headers=headers,
                json={"password": "sehr-sicher-123", "confirm": True},
            )
        )
        review_task = None
        try:
            await asyncio.wait_for(reset_locked.wait(), 5)
            review_task = asyncio.create_task(
                client.post(
                    f"/api/v1/study-sessions/{session['id']}/reviews",
                    headers=headers,
                    json={
                        "idempotency_key": str(uuid.uuid4()),
                        "item_id": item["item_id"],
                        "base_version": item["state_version"],
                        "response": {
                            "type": "typing",
                            "answer": "alternative",
                            "rating": 2,
                            "accept_as_correct": True,
                        },
                    },
                )
            )
            await asyncio.wait_for(review_waiting.wait(), 5)
            assert not review_task.done()
            release_reset.set()
            reset, review = await asyncio.wait_for(asyncio.gather(reset_task, review_task), 5)
            assert reset.status_code == 204, reset.text
            assert review.status_code == 404, review.text
            async with app.state.session_factory() as db:
                for model in [UserCardProgress, ReviewEvent, StudySession]:
                    assert (
                        list(await db.scalars(select(model).where(model.user_id == user_id))) == []
                    )
        finally:
            release_reset.set()
            await asyncio.gather(
                reset_task, *([review_task] if review_task else []), return_exceptions=True
            )
            async with app.state.session_factory() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.execute(delete(Deck).where(Deck.id == deck.id))
                await db.commit()
