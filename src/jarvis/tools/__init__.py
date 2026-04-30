"""Tool & command registry. Importing this package registers all built-in handlers."""

from jarvis.tools import commands  # noqa: F401  — registers /start /help /ping
