"""Logging utilities for Xians SDK v1."""

import logging
import sys
from typing import Any


def setup_logging(
    level: str = "INFO",
    name: str = "xians",
    structured: bool = False,
) -> logging.Logger:
    """
    Configure logging for the Xians SDK.

    Sets up a logger with the specified level and format. Can optionally
    enable structured logging output.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        name: Logger name (default: "xians").
        structured: Enable structured logging output (default: False).

    Returns:
        Configured Logger instance.

    Example:
        >>> logger = setup_logging(level="DEBUG")
        >>> logger.info("SDK initialized")
    """
    logger = logging.getLogger(name)

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid adding multiple handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)

        if structured:
            # For structured logging, use a more detailed format
            formatter = logging.Formatter(
                fmt='{"time": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        else:
            # Standard format
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


__all__ = ["setup_logging"]
