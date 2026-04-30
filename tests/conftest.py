"""Shared pytest fixtures. Each test gets a clean Settings instance and a fresh registry."""

from __future__ import annotations

import os

# Provide defaults BEFORE any jarvis imports so collection-time imports of the
# Celery app (which calls get_settings()) don't fail. Individual tests override
# with monkeypatch as needed.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "collection-default-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "collection-default-secret")

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from jarvis.core.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Set required env vars and return a fresh Settings."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-12345")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "111,222")
    monkeypatch.setenv("ENV", "test")
    return get_settings()


@pytest.fixture
def fake_redis() -> Iterator[Any]:
    """In-memory async Redis stand-in for the idempotency module."""
    from fakeredis.aioredis import FakeRedis  # type: ignore[import-not-found]

    fake = FakeRedis(decode_responses=True)
    with (
        patch("jarvis.core.idempotency._client", fake),
        patch("jarvis.core.idempotency.get_redis", return_value=fake),
    ):
        yield fake
