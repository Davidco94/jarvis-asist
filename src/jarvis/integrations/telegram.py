"""aiogram client + send helpers. Single Bot instance per process."""

from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from jarvis.core.exceptions import TelegramError
from jarvis.core.logging import get_logger
from jarvis.core.settings import get_settings

log = get_logger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    """Lazy singleton aiogram Bot."""
    global _bot
    if _bot is None:
        _bot = Bot(
            token=get_settings().telegram_bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


async def send_message(chat_id: int, text: str, *, reply_to: int | None = None) -> None:
    """Send a text message. Raises TelegramError on API failure."""
    bot = get_bot()
    try:
        await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to)
    except Exception as exc:
        log.error("telegram_send_failed", chat_id=chat_id, error=str(exc))
        raise TelegramError(f"send_message failed: {exc}") from exc


async def close_bot() -> None:
    """Close the underlying aiohttp session. Call on shutdown."""
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
