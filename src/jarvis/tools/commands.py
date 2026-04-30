"""Slash-command registry. Plugin pattern: handlers self-register on import.

Architectural rule: commands are checked BEFORE the LLM agent. They never call the LLM,
never trace to LangSmith, and never count against token budgets.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

CommandHandler = Callable[[str], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Metadata for a registered slash-command."""

    name: str  # canonical name without the leading slash, e.g. "ping"
    description: str  # one-liner shown by /help
    handler: CommandHandler  # async (raw_args: str) -> response_text


_REGISTRY: dict[str, CommandSpec] = {}


def register(name: str, description: str) -> Callable[[CommandHandler], CommandHandler]:
    """Decorator: register a slash-command handler.

    Usage:
        @register("ping", "Liveness check")
        async def _(_args: str) -> str: ...
    """

    def decorator(fn: CommandHandler) -> CommandHandler:
        if name in _REGISTRY:
            raise ValueError(f"command /{name} already registered")
        _REGISTRY[name] = CommandSpec(name=name, description=description, handler=fn)
        return fn

    return decorator


def parse(text: str) -> tuple[str, str] | None:
    """Return (cmd_name, raw_args) if `text` is a registered slash-command, else None.

    Telegram-style: /name or /name@botusername, optionally followed by args.
    """
    text = text.strip()
    if not text.startswith("/"):
        return None
    head, _, args = text[1:].partition(" ")
    # Strip @botusername suffix that Telegram adds in groups.
    name = head.split("@", 1)[0].lower()
    if name not in _REGISTRY:
        return None
    return name, args.strip()


async def dispatch(name: str, args: str) -> str:
    """Run the handler for `name`. Caller must have validated via parse()."""
    spec = _REGISTRY[name]
    return await spec.handler(args)


def list_commands() -> list[CommandSpec]:
    """All registered commands, sorted by name. For /help."""
    return sorted(_REGISTRY.values(), key=lambda c: c.name)


# ── Built-in Phase 0 commands ──────────────────────────────────────────────


@register("start", "Welcome message")
async def _start(_args: str) -> str:
    return (
        "Hi. I'm Jarvis, in Phase 0 — I currently echo your messages.\n"
        "Try /help to see what I can do."
    )


@register("help", "List available commands")
async def _help(_args: str) -> str:
    lines = ["Available commands:"]
    for cmd in list_commands():
        lines.append(f"/{cmd.name} — {cmd.description}")
    return "\n".join(lines)


@register("ping", "Liveness + server time check")
async def _ping(_args: str) -> str:
    return f"pong — {datetime.now(UTC).isoformat(timespec='seconds')}"
