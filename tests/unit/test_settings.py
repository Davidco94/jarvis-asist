"""US-0.11: pydantic-settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jarvis.core.settings import Settings, get_settings


def test_missing_required_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_user_id_csv_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "y")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "1, 2,3")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.allowed_telegram_user_ids == [1, 2, 3]


def test_secret_str_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "highly-secret")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "also-secret")
    settings = Settings()  # type: ignore[call-arg]
    assert "highly-secret" not in repr(settings)
    assert "also-secret" not in repr(settings)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "a")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "b")
    a = get_settings()
    b = get_settings()
    assert a is b
