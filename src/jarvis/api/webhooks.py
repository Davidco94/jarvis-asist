"""Telegram webhook handler.

Stays under 50ms: validates, deduplicates, allowlists, enqueues. Never blocks on I/O
beyond a single Redis SETNX and a Celery .delay() call.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request, status

from jarvis.core.idempotency import claim_update
from jarvis.core.logging import get_logger
from jarvis.core.security import is_user_allowed, verify_telegram_secret
from jarvis.workers.tasks import process_telegram_update

log = get_logger(__name__)
router = APIRouter()


@router.post("/webhooks/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Receive a Telegram update.

    Returns 200 on accept, dedup, and silent-drop. 403 only when the secret token is wrong.
    Telegram retries on non-2xx — silent drops keep the queue clean.
    """
    if not verify_telegram_secret(x_telegram_bot_api_secret_token):
        log.warning("webhook_bad_secret")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    try:
        payload = await request.json()
        update = Update.model_validate(payload)
    except Exception as exc:
        log.warning("webhook_invalid_payload", error=str(exc))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from exc

    structlog.contextvars.bind_contextvars(correlation_id=update.update_id)

    message = update.message
    if message is None or message.text is None or message.from_user is None:
        # Edits, callbacks, channel posts, etc. — Phase 0 ignores everything but text.
        log.info("webhook_unsupported_update_type")
        return {"status": "ignored"}

    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        log.warning(
            "webhook_user_blocked",
            blocked_user_id=user_id,
            username=message.from_user.username,
        )
        return {"status": "blocked"}

    if not await claim_update(update.update_id):
        log.info("webhook_duplicate", update_id=update.update_id)
        return {"status": "duplicate"}

    process_telegram_update.delay(
        update_id=update.update_id,
        chat_id=message.chat.id,
        user_id=user_id,
        message_id=message.message_id,
        text=message.text,
    )
    log.info("webhook_enqueued", update_id=update.update_id)
    return {"status": "enqueued"}
