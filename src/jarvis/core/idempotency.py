"""Idempotency check via Redis SETNX. Used by webhook (per-update) and tools (per-call)."""

from __future__ import annotations

from redis.asyncio import Redis

from jarvis.core.settings import get_settings

_WEBHOOK_TTL_SECONDS = 86_400  # 24h — Telegram retries within this window


_client: Redis[str] | None = None


def get_redis() -> Redis[str]:
    """Lazy singleton async Redis client."""
    global _client
    if _client is None:
        _client = Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
        )
    return _client


async def claim_update(update_id: int) -> bool:
    """True iff this update_id is new and should be processed.

    SET NX EX is atomic: first caller wins, subsequent callers within TTL get False.
    """
    key = f"processed:telegram:{update_id}"
    result = await get_redis().set(key, "1", nx=True, ex=_WEBHOOK_TTL_SECONDS)
    return bool(result)
