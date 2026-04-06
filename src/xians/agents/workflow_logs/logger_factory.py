"""Centralized logger factory — mirrors C# Common.Infrastructure.LoggerFactory.

Provides:
- ``parse_log_level()``  — parse env-var strings like "DEBUG", "INFO" to Python logging levels
- ``get_console_log_level()`` / ``get_server_log_level()`` — resolve from override or env var
- ``configure_log_levels()`` — programmatic override (called during platform init)
- ``setup_root_logging()``  — one-shot root logger config with console + API handler
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .constants import (
    API_LOG_LEVEL_ENV,
    CONSOLE_LOG_LEVEL_ENV,
    DEFAULT_CONSOLE_LOG_LEVEL,
    DEFAULT_SERVER_LOG_LEVEL,
    SERVER_LOG_LEVEL_ENV,
    WORKFLOW_LOG_TO_CONSOLE_ENV,
)

__all__ = [
    "parse_log_level",
    "get_console_log_level",
    "get_server_log_level",
    "should_log_workflow_to_console",
    "configure_log_levels",
    "setup_root_logging",
    "reset",
]

_LEVEL_MAP: dict[str, int] = {
    "TRACE": logging.DEBUG - 5,
    "DEBUG": logging.DEBUG,
    "INFORMATION": logging.INFO,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_console_log_level_override: Optional[int] = None
_server_log_level_override: Optional[int] = None
_setup_done: bool = False


def parse_log_level(level_string: str | None, *, default: int = logging.INFO) -> int:
    """Parse a log-level string to a Python ``logging`` level integer.

    Accepts all names used by the C# SDK: TRACE, DEBUG, INFORMATION, INFO,
    WARNING, WARN, ERROR, CRITICAL (case-insensitive).
    """
    if not level_string:
        return default
    return _LEVEL_MAP.get(level_string.strip().upper(), default)


def get_console_log_level() -> int:
    """Resolve console log level: override → env var → default (DEBUG)."""
    if _console_log_level_override is not None:
        return _console_log_level_override
    return parse_log_level(
        os.environ.get(CONSOLE_LOG_LEVEL_ENV),
        default=parse_log_level(DEFAULT_CONSOLE_LOG_LEVEL),
    )


def get_server_log_level() -> int:
    """Resolve server log level: override → SERVER_LOG_LEVEL → API_LOG_LEVEL → default (ERROR).

    Falls back to legacy ``API_LOG_LEVEL`` for backward compatibility, matching C#.
    """
    if _server_log_level_override is not None:
        return _server_log_level_override

    server_env = os.environ.get(SERVER_LOG_LEVEL_ENV)
    if server_env:
        return parse_log_level(server_env, default=parse_log_level(DEFAULT_SERVER_LOG_LEVEL))

    return parse_log_level(
        os.environ.get(API_LOG_LEVEL_ENV),
        default=parse_log_level(DEFAULT_SERVER_LOG_LEVEL),
    )


def should_log_workflow_to_console() -> bool:
    """Whether workflow logs should also go to the standard logger (console + server).

    Mirrors C# ``WorkflowLoggingHelper.ShouldLogWorkflowToConsole()``.
    Defaults to ``True``; set ``WORKFLOW_LOG_TO_CONSOLE=false`` or ``0`` to disable.
    """
    val = os.environ.get(WORKFLOW_LOG_TO_CONSOLE_ENV, "").strip().lower()
    if not val:
        return True
    return val not in ("false", "0", "no")


def configure_log_levels(
    console_log_level: int | None = None,
    server_log_level: int | None = None,
) -> None:
    """Programmatic override for log levels (called during platform init).

    Mirrors C# ``LoggerFactory.ConfigureLogLevels()``.
    """
    global _console_log_level_override, _server_log_level_override, _setup_done
    _console_log_level_override = console_log_level
    _server_log_level_override = server_log_level
    _setup_done = False  # force re-setup on next call


def setup_root_logging(*, enable_api_logging: bool = True) -> None:
    """Configure the root Python logger with console output and optionally the API handler.

    Idempotent — repeated calls are safe (handlers are only added once).
    Mirrors the C# ``LoggerFactory.CreateLoggerFactoryWithApiLogging()`` pattern.
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    root = logging.getLogger()
    console_level = get_console_log_level()

    # Set root to TRACE equivalent so individual handlers can filter
    root.setLevel(min(console_level, logging.DEBUG))

    _has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    )
    if not _has_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)-8s %(name)s — %(message)s", datefmt="%H:%M:%S")
        )
        root.addHandler(console_handler)

    if enable_api_logging:
        from .api_logger_handler import ApiLoggerHandler

        _has_api = any(isinstance(h, ApiLoggerHandler) for h in root.handlers)
        if not _has_api:
            api_handler = ApiLoggerHandler()
            root.addHandler(api_handler)


def reset() -> None:
    """Reset overrides (for tests)."""
    global _console_log_level_override, _server_log_level_override, _setup_done
    _console_log_level_override = None
    _server_log_level_override = None
    _setup_done = False
