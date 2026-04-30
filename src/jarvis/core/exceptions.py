"""Domain exceptions. Subclass these — never raise plain Exception in app code."""

from __future__ import annotations


class JarvisError(Exception):
    """Base for all Jarvis exceptions."""


class ConfigError(JarvisError):
    """Misconfigured environment / settings."""


class IntegrationError(JarvisError):
    """Failure talking to an external service (Telegram, Anthropic, Google)."""


class TelegramError(IntegrationError):
    """Telegram Bot API call failed."""
