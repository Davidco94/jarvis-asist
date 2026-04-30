"""Celery task: process a single Telegram update.

Phase 0 flow:
    1. Slash-command short-circuit (US-0.12)
    2. Otherwise: echo with 2s delay (US-0.9)
    3. Send via Telegram Bot API
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from celery.exceptions import SoftTimeLimitExceeded

from jarvis.core.logging import get_logger
from jarvis.integrations.telegram import close_bot, send_message
from jarvis.tools import commands
from jarvis.workers.celery_app import celery_app

log = get_logger(__name__)

_ECHO_DELAY_SECONDS = 2.0


@celery_app.task(
    name="jarvis.process_telegram_update",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def process_telegram_update(
    self: Any,  # Celery task self
    *,
    update_id: int,
    chat_id: int,
    user_id: int,
    message_id: int,
    text: str,
) -> None:
    """Synchronous Celery entrypoint that runs the async pipeline."""
    structlog.contextvars.bind_contextvars(
        correlation_id=update_id,
        user_id=user_id,
    )
    try:
        asyncio.run(
            _process(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            )
        )
    except SoftTimeLimitExceeded:
        log.warning("task_soft_timeout", task_id=self.request.id)
        raise
    finally:
        structlog.contextvars.clear_contextvars()


async def _process(*, chat_id: int, message_id: int, text: str) -> None:
    """Async body: dispatch to slash-command or echo, then send response."""
    log.info("processing_update", message_id=message_id, message_text=text)

    parsed = commands.parse(text)
    if parsed is not None:
        cmd_name, args = parsed
        log.info("command_dispatch", command=cmd_name)
        try:
            response = await commands.dispatch(cmd_name, args)
        except Exception:
            log.exception("command_handler_failed", command=cmd_name)
            response = "Sorry — that command failed. Check logs."
    else:
        # Phase 0: echo. Phase 1+ this branch invokes the LangGraph agent.
        await asyncio.sleep(_ECHO_DELAY_SECONDS)
        response = f"echo: {text}"

    try:
        await send_message(chat_id=chat_id, text=response, reply_to=message_id)
        log.info("response_sent")
    finally:
        await close_bot()
