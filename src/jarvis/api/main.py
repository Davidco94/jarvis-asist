"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from jarvis.api import health, webhooks
from jarvis.core.logging import configure_logging, get_logger
from jarvis.integrations.telegram import close_bot

# Force registration of slash-commands on import.
from jarvis.tools import commands  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(service="api")
    log = get_logger(__name__)
    log.info("api_startup")
    try:
        yield
    finally:
        await close_bot()
        log.info("api_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jarvis",
        version="0.0.1",
        lifespan=lifespan,
        docs_url=None,  # no public schema in prod; flip on for dev if needed
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(webhooks.router)
    app.include_router(health.router)
    return app


app = create_app()
