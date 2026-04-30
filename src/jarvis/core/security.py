"""Security helpers: allowlist check, secret-token compare."""

from __future__ import annotations

import hmac

from jarvis.core.settings import get_settings


def is_user_allowed(user_id: int) -> bool:
    """True iff the Telegram user_id is in the configured allowlist."""
    return user_id in get_settings().allowed_telegram_user_ids


def verify_telegram_secret(received: str | None) -> bool:
    """Constant-time compare of the X-Telegram-Bot-Api-Secret-Token header."""
    if not received:
        return False
    expected = get_settings().telegram_webhook_secret.get_secret_value()
    return hmac.compare_digest(received.encode(), expected.encode())
