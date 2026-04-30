"""Celery application factory.

Configured with acks_late so a crashed worker re-delivers — this MAKES tool-call
idempotency mandatory once Phase 1 lands (see US-X.7).
"""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init

from jarvis.core.logging import configure_logging
from jarvis.core.settings import get_settings


def _build() -> Celery:
    settings = get_settings()
    app = Celery(
        "jarvis",
        broker=settings.broker_url,
        backend=settings.result_backend,
        include=["jarvis.workers.tasks"],
    )
    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_time_limit=60,
        task_soft_time_limit=45,
        task_default_retry_delay=2,
        task_default_max_retries=3,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        timezone="UTC",
        enable_utc=True,
    )
    return app


celery_app = _build()


@worker_process_init.connect
def _init_worker_logging(**_: object) -> None:
    """Each worker process re-initializes structlog (forks lose configuration)."""
    configure_logging(service="worker")
