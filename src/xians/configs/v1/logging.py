import logging
import sys
from pathlib import Path
from typing import Any

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

# Logger namespaces pinned above the root level to reduce console noise.
# Keys are logger names/prefixes and values are the minimum level to emit.
#
# - HTTP transports are noisy at DEBUG/INFO, so clamp them to WARNING.
# - Temporal internals (workflow/worker/sandbox chatter) are often noisy at
#   INFO/WARNING in local dev; clamp to ERROR so only actionable failures show.
_NOISY_LOGGERS: dict[str, int] = {
    "httpcore": logging.WARNING,
    "httpx": logging.WARNING,
    "hpack": logging.WARNING,
    "urllib3": logging.WARNING,
    "temporalio": logging.ERROR,
    "temporalio.workflow": logging.ERROR,
    "temporalio.worker": logging.ERROR,
    "temporalio.worker._worker": logging.ERROR,
    "temporalio.worker.workflow_sandbox": logging.ERROR,
}


def _get_root_level(console_level: int) -> int:
    """Return the lowest possible root level so the ApiLogHandler receives
    all records regardless of the console threshold.

    Matches C#: ``builder.SetMinimumLevel(LogLevel.Trace)``
    The console handler's own ``setLevel()`` still gates console output.
    """
    try:
        from ...logging.trace_level import TRACE as _TRACE
        return min(console_level, _TRACE)
    except ImportError:
        return console_level


def _suppress_noisy_loggers() -> None:
    """Pin noisy logger namespaces above the console/root threshold."""
    for name, level in _NOISY_LOGGERS.items():
        logging.getLogger(name).setLevel(level)


def configure_logging(
    log_level: str = "INFO",
    enable_structured: bool = False,
    log_file: Path | None = None,
    log_format: str | None = None,
) -> None:
    try:
        from ...logging.trace_level import register_trace_level
        register_trace_level()
    except ImportError:
        pass

    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    if enable_structured and STRUCTLOG_AVAILABLE:
        _configure_structlog(numeric_level, log_file)
    else:
        _configure_standard_logging(numeric_level, log_file, log_format)


def _configure_structlog(log_level: int, log_file: Path | None = None) -> None:
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handlers = []
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True)
        )
    )
    handlers.append(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer()
            )
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=_get_root_level(log_level),
        handlers=handlers,
    )
    _suppress_noisy_loggers()


def _configure_standard_logging(
    log_level: int,
    log_file: Path | None = None,
    log_format: str | None = None,
) -> None:
    if log_format is None:
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )

    handlers = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=_get_root_level(log_level),
        handlers=handlers,
        format=log_format,
        force=True,
    )
    _suppress_noisy_loggers()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_context(**kwargs: Any) -> dict[str, Any]:
    return kwargs


class LoggerMixin:
    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__module__)
        return self._logger


__all__ = [
    "configure_logging",
    "get_logger",
    "log_context",
    "LoggerMixin",
    "STRUCTLOG_AVAILABLE",
]
