from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DATABASE_PASSWORD = "verba_local_only"
EXAMPLE_DATABASE_PASSWORD = "replace-with-a-long-random-password"
MIN_PRODUCTION_DATABASE_PASSWORD_LENGTH = 16


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    app_name: str = "Verba API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = ""
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "verba"
    database_user: str = "verba"
    database_password: str = LOCAL_DATABASE_PASSWORD
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cookie_secure: bool = False
    cookie_domain: str | None = None
    session_days: int = 30
    content_data_path: Path = Path(__file__).resolve().parents[2] / "data" / "decks"
    max_request_bytes: int = 65_536
    max_import_bytes: int = 10_485_760
    auto_create_schema: bool = False

    @field_validator("allowed_origins", "allowed_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def production_security(self) -> "Settings":
        uses_database_components = not self.database_url.strip()
        is_production = self.environment.casefold() == "production"

        if uses_database_components:
            if is_production and (
                self.database_password in {LOCAL_DATABASE_PASSWORD, EXAMPLE_DATABASE_PASSWORD}
                or len(self.database_password) < MIN_PRODUCTION_DATABASE_PASSWORD_LENGTH
            ):
                raise ValueError(
                    "DATABASE_PASSWORD must be at least 16 characters and must not "
                    "use a known fallback or example value in production"
                )
            password = quote(self.database_password, safe="")
            self.database_url = (
                f"postgresql+asyncpg://{quote(self.database_user, safe='')}:{password}"
                f"@{self.database_host}:{self.database_port}/{quote(self.database_name, safe='')}"
            )
        if not is_production:
            return self
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.allowed_origins):
            raise ValueError("ALLOWED_ORIGINS must use the production origin")
        if any(host in {"localhost", "127.0.0.1"} for host in self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS must use production host names")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
