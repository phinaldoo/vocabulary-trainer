import pytest
from pydantic import ValidationError

from app.config import Settings


def test_database_url_percent_encodes_credentials() -> None:
    settings = Settings(
        _env_file=None,
        database_url="",
        database_user="verba@example",
        database_password="p@ss:/#%",
        database_name="latein kurs",
    )

    assert settings.database_url == (
        "postgresql+asyncpg://verba%40example:p%40ss%3A%2F%23%25@localhost:5432/latein%20kurs"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"cookie_secure": False},
        {"allowed_origins": ["http://localhost:3000"]},
        {"allowed_hosts": ["127.0.0.1"]},
    ],
)
def test_production_settings_fail_closed(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": "",
        "database_password": "a-long-production-password",
        "environment": "production",
        "cookie_secure": True,
        "allowed_origins": ["https://verba.example"],
        "allowed_hosts": ["verba.example"],
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        Settings(**values)


def test_production_settings_accept_secure_component_configuration() -> None:
    settings = Settings(
        _env_file=None,
        database_url="",
        database_password="a-long-production-password",
        environment="production",
        cookie_secure=True,
        allowed_origins=["https://verba.example"],
        allowed_hosts=["verba.example"],
    )

    assert settings.cookie_secure is True
    assert settings.database_url.startswith("postgresql+asyncpg://verba:")


@pytest.mark.parametrize(
    "database_password",
    ["verba_local_only", "replace-with-a-long-random-password", "too-short"],
)
def test_production_component_database_rejects_weak_password(
    database_password: str,
) -> None:
    with pytest.raises(ValidationError, match="DATABASE_PASSWORD must be at least 16"):
        Settings(
            _env_file=None,
            database_url="",
            database_password=database_password,
            environment="production",
            cookie_secure=True,
            allowed_origins=["https://verba.example"],
            allowed_hosts=["verba.example"],
        )


def test_production_explicit_database_url_ignores_unused_component_password() -> None:
    database_url = "postgresql+asyncpg://verba:managed-secret@db.example/verba"

    settings = Settings(
        _env_file=None,
        database_url=database_url,
        database_password="too-short",
        environment="production",
        cookie_secure=True,
        allowed_origins=["https://verba.example"],
        allowed_hosts=["verba.example"],
    )

    assert settings.database_url == database_url
