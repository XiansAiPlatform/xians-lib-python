"""Standardized logging configuration for Xians SDK v1."""

import logging
import sys
from pathlib import Path
from typing import Any

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


def configure_logging(
    log_level: str = "INFO",
    enable_structured: bool = False,
    log_file: Path | None = None,
    log_format: str | None = None,
) -> None:
    """
    Configure standardized logging for the SDK.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        enable_structured: Enable structured logging with structlog (if available).
        log_file: Optional file path for logging output.
        log_format: Custom log format string (only for standard logging).

    Example:
        >>> configure_logging(log_level="DEBUG", enable_structured=True)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # Configure structured logging if requested and available
    if enable_structured and STRUCTLOG_AVAILABLE:
        _configure_structlog(numeric_level, log_file)
    else:
        _configure_standard_logging(numeric_level, log_file, log_format)


def _configure_structlog(log_level: int, log_file: Path | None = None) -> None:
    """Configure structured logging with structlog."""
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

    # Configure standard library logging
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True)
        )
    )
    handlers.append(console_handler)

    # File handler if specified
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

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
    )


def _configure_standard_logging(
    log_level: int,
    log_file: Path | None = None,
    log_format: str | None = None,
) -> None:
    """Configure standard Python logging."""
    if log_format is None:
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )

    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format=log_format,
        force=True,  # Override existing configuration
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with standardized configuration.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Operation completed")
    """
    return logging.getLogger(name)


def log_context(**kwargs: Any) -> dict[str, Any]:
    """
    Create a logging context dictionary for structured logging.
    """
    return kwargs


class LoggerMixin:
    """
    Mixin class to add logging capabilities to any class.
    """

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__module__)
        return self._logger


def setup_logging(level: str = "INFO", structured: bool = False) -> logging.Logger:
    """Configure logging and return the root Xians logger.
    """

    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    configure_logging(log_level=level, enable_structured=structured)
    logger = logging.getLogger("xians")
    logger.setLevel(numeric_level)
    return logger


__all__ = [
    "configure_logging",
    "get_logger",
    "log_context",
    "LoggerMixin",
    "STRUCTLOG_AVAILABLE",
    "setup_logging",
]
