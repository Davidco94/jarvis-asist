"""Health endpoint: verifies Redis connectivity. Postgres added in Phase 1."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from jarvis.core.idempotency import get_redis
from jarvis.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    redis: bool
    # postgres: bool — added in Phase 1 once we actually use the DB.


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    redis_ok = False
    try:
        redis_ok = bool(await get_redis().ping())
    except Exception as exc:
        log.warning("health_redis_unreachable", error=str(exc))

    return HealthResponse(
        status="ok" if redis_ok else "degraded",
        redis=redis_ok,
    )
