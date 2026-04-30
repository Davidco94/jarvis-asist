"""US-0.5: Redis-backed idempotency."""

from __future__ import annotations

from typing import Any

import pytest

from jarvis.core.idempotency import claim_update
from jarvis.core.settings import Settings


@pytest.mark.asyncio
async def test_first_claim_wins(settings_env: Settings, fake_redis: Any) -> None:
    assert await claim_update(42) is True


@pytest.mark.asyncio
async def test_duplicate_claim_loses(settings_env: Settings, fake_redis: Any) -> None:
    assert await claim_update(42) is True
    assert await claim_update(42) is False


@pytest.mark.asyncio
async def test_distinct_updates_independent(settings_env: Settings, fake_redis: Any) -> None:
    assert await claim_update(1) is True
    assert await claim_update(2) is True
    assert await claim_update(1) is False
    assert await claim_update(2) is False


@pytest.mark.asyncio
async def test_ttl_set(settings_env: Settings, fake_redis: Any) -> None:
    """Claim sets a 24h TTL — guards against forever-keys filling Redis."""
    await claim_update(7)
    ttl = await fake_redis.ttl("processed:telegram:7")
    assert 86_000 < ttl <= 86_400
