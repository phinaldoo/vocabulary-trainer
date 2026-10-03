import random
import uuid
from collections import Counter

import pytest
from httpx import ASGITransport, AsyncClient
from learner_fixtures import make_deck
from sqlalchemy import select
from test_api_workflows import _mutation_headers, _register, _settings

from app.main import create_app
from app.models import Card, UserCardPreference, UserCardProgress
from app.schemas import StudySessionCreate
from app.services.study import random_selection


@pytest.mark.asyncio
async def test_catalogue_sorts_before_pagination_and_validates_sort_keys():
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        await _register(client, "sort@example.com")
        deck, sections, cards = await make_deck(app)
        base = f"/api/v1/cards?deck_id={deck.id}"
        page = (await client.get(f"{base}&sort_by=front&page_size=2&page=2")).json()
        assert [c["front_text"] for c in page["items"]] == ["word-3", "word-4"]
        assert page["total"] == 6
        descending = (await client.get(f"{base}&sort_by=back&sort_direction=desc")).json()
        assert [c["back_text"] for c in descending["items"]] == [
            f"answer-{i}" for i in range(5, -1, -1)
        ]
        async with app.state.session_factory() as db:
            first = await db.get(Card, cards[0].id)
            first.details = {
                "genus": "a",
                "partOfSpeech": "adjective",
                "info": "aaa",
                "note": "aaa",
            }
            last = await db.get(Card, cards[-1].id)
            last.details = {}
            await db.commit()
        for key in ["gender", "part_of_speech", "additional_info", "additional_info_2"]:
            for direction in ["asc", "desc"]:
                result = await client.get(f"{base}&sort_by={key}&sort_direction={direction}")
                assert result.status_code == 200, result.text
                ids = [c["id"] for c in result.json()["items"]]
                assert ids[-1] == str(cards[-1].id)  # Missing values always sort last.
                assert ids[0 if direction == "asc" else -2] == str(cards[0].id)
        scoped = (await client.get(f"{base}&section_id={sections[0].id}&sort_by=front")).json()
        assert scoped["total"] == 2
        assert all(c["section_id"] == str(sections[0].id) for c in scoped["items"])
        assert (await client.get(f"{base}&sort_by=unknown")).status_code == 422
        assert (await client.get(f"{base}&sort_direction=unknown")).status_code == 422


@pytest.mark.asyncio
async def test_difficulty_is_personal_persistent_and_does_not_fabricate_reviews():
    app = create_app(_settings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as one,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as two,
    ):
        await _register(one, "one@example.com")
        await _register(two, "two@example.com")
        deck, _, cards = await make_deck(app)
        headers = _mutation_headers(one)
        path = f"/api/v1/cards/{cards[0].id}/difficulty"
        assert (await one.put(path, json={"difficulty": "hard"})).status_code == 403
        for value in ["normal", "easy", "hard", "hard"]:
            saved = await one.put(path, headers=headers, json={"difficulty": value})
            assert saved.status_code == 200, saved.text
            assert saved.json() == {"difficulty": value}
        base = f"/api/v1/cards?deck_id={deck.id}"
        difficult = (await one.get(f"{base}&state=difficult")).json()
        assert [c["id"] for c in difficult["items"]] == [str(cards[0].id)]
        assert difficult["items"][0]["status"] == "new"
        assert difficult["items"][0]["difficulty"] == "hard"
        assert (await two.get(f"{base}&state=difficult")).json()["total"] == 0
        assert all(c["difficulty"] == "auto" for c in (await two.get(base)).json()["items"])
        sorted_cards = (await one.get(f"{base}&sort_by=difficulty&sort_direction=desc")).json()
        assert sorted_cards["items"][0]["id"] == str(cards[0].id)
        async with app.state.session_factory() as db:
            assert len(list(await db.scalars(select(UserCardPreference)))) == 1
            assert list(await db.scalars(select(UserCardProgress))) == []
        assert (
            await one.put(path, headers=headers, json={"difficulty": "invalid"})
        ).status_code == 422
        assert (
            await one.put(
                f"/api/v1/cards/{uuid.uuid4()}/difficulty",
                headers=headers,
                json={"difficulty": "hard"},
            )
        ).status_code == 404
        await one.put(path, headers=headers, json={"difficulty": "auto"})
        assert (await one.get(f"{base}&state=difficult")).json()["total"] == 0
        async with app.state.session_factory() as db:
            assert list(await db.scalars(select(UserCardPreference))) == []


def test_personal_difficulty_affects_adaptive_but_not_uniform_random(monkeypatch):
    monkeypatch.setattr("app.services.study.random", random.Random(143))
    cards = [Card(id=uuid.uuid4()), Card(id=uuid.uuid4())]
    difficulty = {cards[0].id: "easy", cards[1].id: "hard"}
    for mode in ["random", "adaptive"]:
        payload = StudySessionCreate(
            deck_id=uuid.uuid4(),
            direction="forward",
            input_mode="typing",
            selection_mode=mode,
            limit=1,
        )
        counts = Counter(
            random_selection(cards, {}, payload, difficulty)[0][0].id for _ in range(4000)
        )
        if mode == "adaptive":
            assert counts[cards[1].id] > counts[cards[0].id] * 3
        else:
            assert all(1800 < count < 2200 for count in counts.values())
