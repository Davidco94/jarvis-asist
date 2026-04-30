"""structlog configuration. JSON in prod, pretty in dev. Same pipeline for api + worker."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars
from structlog.types import EventDict, Processor

from jarvis.core.settings import get_settings


def _redact_pii(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Drop PII fields unless LOG_PII=true. Add new sensitive keys here."""
    if get_settings().log_pii:
        return event_dict
    for key in ("message_text", "user_first_name", "user_last_name", "username"):
        if key in event_dict:
            event_dict[key] = "<redacted>"
    return event_dict


def configure_logging(service: str) -> None:
    """Initialize structlog. Call once at process start (api or worker)."""
    settings = get_settings()

    shared: list[Processor] = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_pii,
    ]

    renderer: Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bind service name for every log line in this process.
    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name) if name else structlog.get_logger()
