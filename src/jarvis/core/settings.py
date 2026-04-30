"""Typed application settings, loaded once from env."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Missing required values cause startup failure."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────────────────
    env: Literal["dev", "prod", "test"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_pii: bool = False
    log_format: Literal["json", "pretty"] = "pretty"

    # ── Telegram ───────────────────────────────────────────────────────────
    telegram_bot_token: SecretStr
    telegram_webhook_secret: SecretStr
    telegram_webhook_url: str | None = None
    allowed_telegram_user_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    # ── Redis ──────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Postgres ───────────────────────────────────────────────────────────
    postgres_dsn: str = "postgresql+asyncpg://jarvis:jarvis@postgres:5432/jarvis"

    # ── Celery ─────────────────────────────────────────────────────────────
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # ── HTTP ───────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"  # noqa: S104  — bound inside container, not host network
    api_port: int = 8000

    @field_validator("allowed_telegram_user_ids", mode="before")
    @classmethod
    def _split_csv(cls, v: str | list[int]) -> list[int]:
        """Accept comma-separated env var, e.g. '12345,67890'."""
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once; cached for process lifetime."""
    return Settings()
