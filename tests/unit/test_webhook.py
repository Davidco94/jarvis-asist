"""US-0.4 webhook end-to-end (with Celery task .delay() patched)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from jarvis.api.main import create_app
from jarvis.core.settings import Settings


def _update(update_id: int = 1, user_id: int = 111, text: str = "hello") -> dict[str, Any]:
    """Minimal valid Telegram Update payload."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": 99,
            "date": 1_700_000_000,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Tester"},
            "text": text,
        },
    }


@pytest.fixture
def client(settings_env: Settings, fake_redis: Any) -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def patched_task() -> Any:
    with patch("jarvis.api.webhooks.process_telegram_update") as mock:
        yield mock


def test_bad_secret_returns_403(client: TestClient, patched_task: Any) -> None:
    resp = client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG"},
        json=_update(),
    )
    assert resp.status_code == 403
    patched_task.delay.assert_not_called()


def test_missing_secret_returns_403(client: TestClient, patched_task: Any) -> None:
    resp = client.post("/webhooks/telegram", json=_update())
    assert resp.status_code == 403


def test_invalid_payload_returns_422(client: TestClient, patched_task: Any) -> None:
    resp = client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"not": "a real update"},
    )
    assert resp.status_code == 422


def test_blocked_user_silently_dropped(client: TestClient, patched_task: Any) -> None:
    resp = client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json=_update(user_id=999),
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "blocked"}
    patched_task.delay.assert_not_called()


def test_happy_path_enqueues(client: TestClient, patched_task: Any) -> None:
    resp = client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json=_update(update_id=42, text="hi"),
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "enqueued"}
    patched_task.delay.assert_called_once()
    kwargs = patched_task.delay.call_args.kwargs
    assert kwargs["update_id"] == 42
    assert kwargs["text"] == "hi"


def test_duplicate_update_silently_dropped(client: TestClient, patched_task: Any) -> None:
    payload = _update(update_id=7)
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}
    first = client.post("/webhooks/telegram", headers=headers, json=payload)
    second = client.post("/webhooks/telegram", headers=headers, json=payload)
    assert first.status_code == 200
    assert first.json() == {"status": "enqueued"}
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate"}
    assert patched_task.delay.call_count == 1


def test_non_text_update_ignored(client: TestClient, patched_task: Any) -> None:
    """Phase 0 handles only text messages."""
    resp = client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"update_id": 100, "edited_message": _update()["message"]},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ignored"}
    patched_task.delay.assert_not_called()
