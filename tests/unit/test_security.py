"""US-0.4 secret-token verification + US-0.6 allowlist."""

from __future__ import annotations

from jarvis.core.security import is_user_allowed, verify_telegram_secret
from jarvis.core.settings import Settings


def test_allowlist_match(settings_env: Settings) -> None:
    assert is_user_allowed(111) is True
    assert is_user_allowed(222) is True


def test_allowlist_block(settings_env: Settings) -> None:
    assert is_user_allowed(999) is False


def test_secret_token_match(settings_env: Settings) -> None:
    assert verify_telegram_secret("test-secret") is True


def test_secret_token_mismatch(settings_env: Settings) -> None:
    assert verify_telegram_secret("wrong") is False


def test_secret_token_missing(settings_env: Settings) -> None:
    assert verify_telegram_secret(None) is False
    assert verify_telegram_secret("") is False
