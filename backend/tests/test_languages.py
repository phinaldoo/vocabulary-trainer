import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.languages import (
    ai_response_language,
    negotiate_ui_language,
    normalize_ui_language,
    parse_accept_language,
)
from app.main import create_app
from app.models import User


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        allowed_origins=["http://testserver"],
        allowed_hosts=["testserver"],
        auto_create_schema=True,
    )


async def _csrf(client: AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _mutation_headers(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get("verba_csrf")
    assert token
    return {"X-CSRF-Token": token, "Origin": "http://testserver"}


def test_language_normalization_and_negotiation() -> None:
    assert normalize_ui_language("en-US") == "en"
    assert normalize_ui_language("de_AT") == "de"
    assert normalize_ui_language("es-MX") == "es"
    assert normalize_ui_language("hi-IN") == "hi"
    assert normalize_ui_language("zh-TW") == "zh-Hans"
    assert normalize_ui_language("fr-FR") is None
    assert negotiate_ui_language(["fr-FR", "es-ES"]) == "es"
    assert negotiate_ui_language(["fr-FR"]) == "en"
    assert parse_accept_language("fr-FR;q=1, de-DE;q=0.8, es;q=0") == ["fr-FR", "de-DE"]
    assert ai_response_language("es") == "es"
    assert ai_response_language(None) == "en"


@pytest.mark.asyncio
async def test_account_language_initialization_and_user_override() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = await _csrf(client)
            registered = await client.post(
                "/api/v1/auth/register",
                headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
                json={
                    "email": "language@example.com",
                    "password": "very-secure-123",
                    "display_name": "Language Test",
                    "language": "es-MX",
                },
            )
            assert registered.status_code == 201, registered.text
            user_id = uuid.UUID(registered.json()["id"])
            assert registered.json()["language"] == "es"

            async with app.state.session_factory() as db:
                user = await db.get(User, user_id)
                assert user
                user.language = None
                await db.commit()

            initialized = await client.post(
                "/api/v1/account/language/initialize",
                headers=_mutation_headers(client),
                json={"language": "zh-Hans"},
            )
            assert initialized.status_code == 200
            assert initialized.json()["language"] == "zh-Hans"

            unchanged = await client.post(
                "/api/v1/account/language/initialize",
                headers=_mutation_headers(client),
                json={"language": "en"},
            )
            assert unchanged.json()["language"] == "zh-Hans"

            settings = await client.patch(
                "/api/v1/account/settings",
                headers=_mutation_headers(client),
                json={
                    "daily_goal": 12,
                    "direction": "forward",
                    "input_mode": "typing",
                    "language": "de",
                    "selected_deck_id": None,
                    "selected_section_id": None,
                },
            )
            assert settings.status_code == 200, settings.text
            assert settings.json()["language"] == "de"


@pytest.mark.asyncio
async def test_first_successful_login_sets_missing_language_only() -> None:
    app = create_app(_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as registration:
            token = await _csrf(registration)
            response = await registration.post(
                "/api/v1/auth/register",
                headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
                json={
                    "email": "legacy@example.com",
                    "password": "very-secure-123",
                    "display_name": "Legacy User",
                    "language": "de",
                },
            )
            user_id = uuid.UUID(response.json()["id"])

        async with app.state.session_factory() as db:
            user = await db.get(User, user_id)
            assert user
            user.language = None
            await db.commit()

        async with AsyncClient(transport=transport, base_url="http://testserver") as failed:
            token = await _csrf(failed)
            response = await failed.post(
                "/api/v1/auth/login",
                headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
                json={"email": "legacy@example.com", "password": "wrong", "language": "hi-IN"},
            )
            assert response.status_code == 401

        async with app.state.session_factory() as db:
            user = await db.get(User, user_id)
            assert user and user.language is None

        async with AsyncClient(transport=transport, base_url="http://testserver") as login:
            token = await _csrf(login)
            response = await login.post(
                "/api/v1/auth/login",
                headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
                json={
                    "email": "legacy@example.com",
                    "password": "very-secure-123",
                    "language": "hi-IN",
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["language"] == "hi"

        async with AsyncClient(transport=transport, base_url="http://testserver") as later_login:
            token = await _csrf(later_login)
            response = await later_login.post(
                "/api/v1/auth/login",
                headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
                json={
                    "email": "legacy@example.com",
                    "password": "very-secure-123",
                    "language": "en-US",
                },
            )
            assert response.status_code == 200
            assert response.json()["language"] == "hi"
