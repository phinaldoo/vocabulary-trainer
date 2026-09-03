import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import Card, User, UserCardProgress


async def _csrf(client: AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


async def _register(client: AsyncClient, email: str) -> dict[str, object]:
    token = await _csrf(client)
    response = await client.post(
        "/api/v1/auth/register",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"email": email, "password": "sehr-sicher-123", "display_name": "Testkonto"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _mutation_headers(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get("vocabulary_trainer_csrf")
    assert token
    return {"X-CSRF-Token": token, "Origin": "http://testserver"}


async def _promote(app, user_id: str) -> None:  # type: ignore[no-untyped-def]
    async with app.state.session_factory() as db:
        user = await db.get(User, uuid.UUID(user_id))
        assert user
        user.role = "admin"
        await db.commit()


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        allowed_origins=["http://testserver"],
        allowed_hosts=["testserver"],
        auto_create_schema=True,
    )


@pytest.mark.asyncio
async def test_first_user_is_admin_and_can_promote_other_users() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as admin:
            first = await _register(admin, "owner@example.com")
            assert first["role"] == "admin"

            async with AsyncClient(transport=transport, base_url="http://testserver") as learner:
                second = await _register(learner, "learner@example.com")
                assert second["role"] == "user"

                forbidden = await learner.get("/api/v1/admin/users")
                assert forbidden.status_code == 403

                users = await admin.get("/api/v1/admin/users?page_size=1")
                assert users.status_code == 200
                assert users.json()["total"] == 2
                assert users.json()["pages"] == 2
                assert users.json()["items"][0]["email"] == "owner@example.com"

                promoted = await admin.post(
                    f"/api/v1/admin/users/{second['id']}/promote",
                    headers=_mutation_headers(admin),
                )
                assert promoted.status_code == 200, promoted.text
                assert promoted.json()["role"] == "admin"

                # Existing sessions pick up the new role on their next request.
                newly_authorized = await learner.get("/api/v1/admin/users")
                assert newly_authorized.status_code == 200


@pytest.mark.asyncio
async def test_account_owner_can_update_name_and_login_email() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await _register(client, "original@example.com")

            updated = await client.patch(
                "/api/v1/account/profile",
                headers=_mutation_headers(client),
                json={
                    "email": "Renamed@Example.com",
                    "display_name": "  Updated Learner  ",
                },
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["email"] == "renamed@example.com"
            assert updated.json()["display_name"] == "Updated Learner"
            assert updated.json()["role"] == registered["role"]

            current = await client.get("/api/v1/auth/me")
            assert current.status_code == 200
            assert current.json()["email"] == "renamed@example.com"
            assert current.json()["display_name"] == "Updated Learner"

            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as other_user:
                await _register(other_user, "taken@example.com")

            conflict = await client.patch(
                "/api/v1/account/profile",
                headers=_mutation_headers(client),
                json={"email": "TAKEN@example.com", "display_name": "Another Name"},
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "email_in_use"

            unchanged = await client.get("/api/v1/auth/me")
            assert unchanged.json()["email"] == "renamed@example.com"
            assert unchanged.json()["display_name"] == "Updated Learner"

        async with AsyncClient(transport=transport, base_url="http://testserver") as login:
            token = await _csrf(login)
            response = await login.post(
                "/api/v1/auth/login",
                headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
                json={"email": "renamed@example.com", "password": "sehr-sicher-123"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["display_name"] == "Updated Learner"


@pytest.mark.asyncio
async def test_admin_shared_catalogue_study_snapshots_and_account_isolation() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as admin:
            admin_user = await _register(admin, "admin@example.com")
            await _promote(app, str(admin_user["id"]))

            created_deck = await admin.post(
                "/api/v1/admin/decks",
                headers=_mutation_headers(admin),
                json={
                    "slug": "english-german",
                    "title": "Englisch – Deutsch",
                    "description": "Gemeinsames Testdeck",
                    "front_label": "Englisch",
                    "back_label": "Deutsch",
                    "front_language": "en",
                    "back_language": "de",
                    "front_matcher": "generic-v1",
                    "back_matcher": "german-v1",
                    "license": "CC0-1.0",
                    "attribution": None,
                },
            )
            assert created_deck.status_code == 201, created_deck.text
            deck = created_deck.json()

            created_section = await admin.post(
                f"/api/v1/admin/decks/{deck['id']}/sections",
                headers=_mutation_headers(admin),
                json={"stable_key": "basics", "title": "Grundlagen", "sort_order": 1},
            )
            assert created_section.status_code == 201, created_section.text
            section = created_section.json()

            cards = []
            for order, front, back in [
                (1, "nuvexa-47", "qarilo-82"),
                (2, "temoru-19", "fyzana-63"),
            ]:
                response = await admin.post(
                    f"/api/v1/admin/decks/{deck['id']}/cards",
                    headers=_mutation_headers(admin),
                    json={
                        "stable_key": front,
                        "section_id": section["id"],
                        "sort_order": order,
                        "front_text": front,
                        "back_text": back,
                        "front_answers": [],
                        "back_answers": [],
                        "metadata": {"kind": "noun"},
                    },
                )
                assert response.status_code == 201, response.text
                cards.append(response.json())

            published = await admin.patch(
                f"/api/v1/admin/decks/{deck['id']}/status",
                headers=_mutation_headers(admin),
                json={"status": "published"},
            )
            assert published.status_code == 200

            admin_page = await admin.get(
                f"/api/v1/admin/decks/{deck['id']}/cards?page=2&page_size=1"
            )
            assert admin_page.status_code == 200
            assert admin_page.json()["total"] == 2
            assert admin_page.json()["pages"] == 2
            assert [item["front_text"] for item in admin_page.json()["items"]] == ["temoru-19"]

            async with AsyncClient(transport=transport, base_url="http://testserver") as learner:
                await _register(learner, "learner@example.com")
                forbidden = await learner.get("/api/v1/admin/decks")
                assert forbidden.status_code == 403

                shared = await learner.get("/api/v1/decks")
                assert shared.status_code == 200
                assert shared.json()[0]["card_count"] == 2

                learner_cards = await learner.get(f"/api/v1/cards?deck_id={deck['id']}")
                admin_cards = await admin.get(f"/api/v1/cards?deck_id={deck['id']}")
                assert learner_cards.json()["total"] == admin_cards.json()["total"] == 2

                learner_page = await learner.get(
                    f"/api/v1/cards?deck_id={deck['id']}&state=new&page=2&page_size=1"
                )
                assert learner_page.status_code == 200
                assert learner_page.json()["total"] == 2
                assert learner_page.json()["pages"] == 2
                assert [item["front_text"] for item in learner_page.json()["items"]] == [
                    "temoru-19"
                ]

                favorite = await learner.put(
                    f"/api/v1/favorites/{cards[0]['id']}",
                    headers=_mutation_headers(learner),
                )
                assert favorite.status_code == 200
                favorites = await learner.get(
                    f"/api/v1/cards?deck_id={deck['id']}&state=favorites&page_size=1"
                )
                assert favorites.status_code == 200
                assert favorites.json()["total"] == 1
                assert favorites.json()["items"][0]["favorite"] is True

                scoped = await admin.post(
                    "/api/v1/study-sessions",
                    headers=_mutation_headers(admin),
                    json={
                        "deck_id": deck["id"],
                        "section_id": section["id"],
                        "direction": "forward",
                        "input_mode": "reveal",
                        "limit": 2,
                    },
                )
                assert scoped.status_code == 200, scoped.text
                session = scoped.json()
                assert session["total"] == 2
                assert {card["section_id"] for card in session["cards"]} == {section["id"]}
                assert all(
                    "solution" not in card and "back_text" not in card for card in session["cards"]
                )

                card = session["cards"][0]
                premature = await admin.post(
                    f"/api/v1/study-sessions/{session['id']}/reviews",
                    headers=_mutation_headers(admin),
                    json={
                        "idempotency_key": str(uuid.uuid4()),
                        "item_id": card["item_id"],
                        "base_version": card["state_version"],
                        "response": {"type": "self_assessment", "known": True},
                    },
                )
                assert premature.status_code == 409
                assert premature.json()["error"]["code"] == "answer_not_revealed"

                revealed = await admin.post(
                    f"/api/v1/study-sessions/{session['id']}/items/{card['item_id']}/reveal",
                    headers=_mutation_headers(admin),
                )
                assert revealed.status_code == 200
                assert revealed.json()["solution"] in {"qarilo-82", "fyzana-63"}

                idempotency_key = str(uuid.uuid4())
                review_payload = {
                    "idempotency_key": idempotency_key,
                    "item_id": card["item_id"],
                    "base_version": card["state_version"],
                    "response": {"type": "self_assessment", "known": False},
                }
                reviewed = await admin.post(
                    f"/api/v1/study-sessions/{session['id']}/reviews",
                    headers=_mutation_headers(admin),
                    json=review_payload,
                )
                assert reviewed.status_code == 200, reviewed.text
                replay = await admin.post(
                    f"/api/v1/study-sessions/{session['id']}/reviews",
                    headers=_mutation_headers(admin),
                    json=review_payload,
                )
                assert replay.json() == reviewed.json()

                difficult = await admin.get(
                    f"/api/v1/cards?deck_id={deck['id']}&state=difficult"
                )
                assert difficult.status_code == 200
                assert difficult.json()["total"] == 1

                typing = await admin.post(
                    "/api/v1/study-sessions",
                    headers=_mutation_headers(admin),
                    json={
                        "deck_id": deck["id"],
                        "section_id": section["id"],
                        "direction": "reverse",
                        "input_mode": "typing",
                        "limit": 1,
                    },
                )
                assert typing.status_code == 200, typing.text
                typing_session = typing.json()
                typing_card = typing_session["cards"][0]
                original_solution = (
                    "nuvexa-47" if typing_card["prompt"] == "qarilo-82" else "temoru-19"
                )
                source_card = next(
                    item for item in cards if item["front_text"] == original_solution
                )
                changed_front = f"changed-{original_solution}"
                updated = await admin.patch(
                    f"/api/v1/admin/decks/{deck['id']}/cards/{source_card['id']}",
                    headers=_mutation_headers(admin),
                    json={
                        "section_id": section["id"],
                        "sort_order": source_card["sort_order"],
                        "front_text": changed_front,
                        "back_text": source_card["back_text"],
                        "front_answers": [],
                        "back_answers": [],
                        "metadata": source_card["metadata"],
                        "active": True,
                    },
                )
                assert updated.status_code == 200, updated.text

                checked = await admin.post(
                    f"/api/v1/study-sessions/{typing_session['id']}/check",
                    headers=_mutation_headers(admin),
                    json={"item_id": typing_card["item_id"], "answer": original_solution},
                )
                assert checked.status_code == 200
                assert checked.json()["correct"] is True
                assert checked.json()["solution"] == original_solution

                progress = await learner.get(f"/api/v1/progress?deck_id={deck['id']}")
                assert progress.status_code == 200
                assert progress.json()["learned"] == 0

                deletion = await admin.request(
                    "DELETE",
                    "/api/v1/account",
                    headers=_mutation_headers(admin),
                    json={"password": "sehr-sicher-123"},
                )
                assert deletion.status_code == 204
                assert (await learner.get("/api/v1/decks")).json()[0]["card_count"] == 2

        async with app.state.session_factory() as db:
            card_count = await db.scalar(select(func.count()).select_from(Card))
            admin_progress = await db.scalar(
                select(func.count())
                .select_from(UserCardProgress)
                .where(UserCardProgress.user_id == uuid.UUID(str(admin_user["id"])))
            )
            assert card_count == 2
            assert admin_progress == 0


@pytest.mark.asyncio
async def test_versioned_manifest_import_is_idempotent_and_conflict_safe() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as admin:
            user = await _register(admin, "importer@example.com")
            await _promote(app, str(user["id"]))
            manifest = {
                "schemaVersion": 1,
                "id": "french-english",
                "version": 1,
                "title": "Französisch – Englisch",
                "description": None,
                "license": "CC0-1.0",
                "attribution": None,
                "front": {"label": "Französisch", "language": "fr", "matcher": "generic-v1"},
                "back": {"label": "Englisch", "language": "en", "matcher": "generic-v1"},
                "sections": [{"id": "basics", "title": "Basics", "order": 1}],
                "cards": [
                    {
                        "id": "bonjour",
                        "section": "basics",
                        "order": 1,
                        "front": {"text": "bonjour", "answers": []},
                        "back": {"text": "hello", "answers": ["hi"]},
                        "metadata": {},
                    }
                ],
            }
            imported = await admin.post(
                "/api/v1/admin/import",
                headers=_mutation_headers(admin),
                json=manifest,
            )
            assert imported.status_code == 200, imported.text
            assert imported.json()["created_cards"] == 1
            repeated = await admin.post(
                "/api/v1/admin/import",
                headers=_mutation_headers(admin),
                json=manifest,
            )
            assert repeated.status_code == 200
            assert repeated.json()["unchanged"] is True

            manifest["cards"][0]["back"]["text"] = "good morning"  # type: ignore[index]
            conflict = await admin.post(
                "/api/v1/admin/import",
                headers=_mutation_headers(admin),
                json=manifest,
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "deck_version_conflict"


@pytest.mark.asyncio
async def test_matcher_change_revalidates_existing_cards() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as admin:
            user = await _register(admin, "matcher-admin@example.com")
            await _promote(app, str(user["id"]))
            deck_response = await admin.post(
                "/api/v1/admin/decks",
                headers=_mutation_headers(admin),
                json={
                    "slug": "matcher-test",
                    "title": "Matcher test",
                    "description": None,
                    "front_label": "Prompt",
                    "back_label": "Answer",
                    "front_language": "en",
                    "back_language": "en",
                    "front_matcher": "generic-v1",
                    "back_matcher": "generic-v1",
                    "license": None,
                    "attribution": None,
                },
            )
            deck = deck_response.json()
            card_response = await admin.post(
                f"/api/v1/admin/decks/{deck['id']}/cards",
                headers=_mutation_headers(admin),
                json={
                    "stable_key": "unbalanced",
                    "section_id": None,
                    "sort_order": 1,
                    "front_text": "foo (bar",
                    "back_text": "answer",
                    "front_answers": [],
                    "back_answers": [],
                    "metadata": {},
                },
            )
            assert card_response.status_code == 201

            incompatible = await admin.patch(
                f"/api/v1/admin/decks/{deck['id']}",
                headers=_mutation_headers(admin),
                json={
                    "title": deck["title"],
                    "description": None,
                    "front_label": deck["front_label"],
                    "back_label": deck["back_label"],
                    "front_language": deck["front_language"],
                    "back_language": deck["back_language"],
                    "front_matcher": "german-v1",
                    "back_matcher": "generic-v1",
                    "license": None,
                    "attribution": None,
                },
            )
            assert incompatible.status_code == 422
            assert incompatible.json()["error"]["code"] == "matcher_incompatible"

            unchanged = await admin.get(f"/api/v1/admin/decks/{deck['id']}")
            assert unchanged.json()["front_matcher"] == "generic-v1"
