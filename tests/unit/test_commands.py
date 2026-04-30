"""US-0.12: slash-command pre-handler."""

from __future__ import annotations

import pytest

from jarvis.tools import commands


def test_parse_known_command() -> None:
    assert commands.parse("/ping") == ("ping", "")
    assert commands.parse("/help") == ("help", "")
    assert commands.parse("/start") == ("start", "")


def test_parse_with_args() -> None:
    assert commands.parse("/help me out") == ("help", "me out")


def test_parse_with_botusername_suffix() -> None:
    """Telegram appends @botusername in groups; we strip it."""
    assert commands.parse("/ping@JarvisBot") == ("ping", "")


def test_parse_unknown_returns_none() -> None:
    assert commands.parse("/nonexistent") is None


def test_parse_non_command_returns_none() -> None:
    assert commands.parse("hello") is None
    assert commands.parse("") is None
    assert commands.parse(" /ping") == ("ping", "")  # leading space ok after strip


@pytest.mark.asyncio
async def test_dispatch_ping() -> None:
    out = await commands.dispatch("ping", "")
    assert out.startswith("pong")


@pytest.mark.asyncio
async def test_dispatch_help_lists_all_commands() -> None:
    out = await commands.dispatch("help", "")
    assert "/start" in out
    assert "/help" in out
    assert "/ping" in out


def test_register_duplicate_raises() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @commands.register("ping", "duplicate")
        async def _(_args: str) -> str:
            return ""
