"""Context-aware logger factory. Matches C# XiansLogger / Logger<T>.

Provides a unified logging API that:
- Logs to the console via Python's standard logging
- Automatically captures workflow/agent context
- Routes logs to the Xians server via ApiLogHandler (when server logging is enabled)

Usage in activities / services::

    from xians.logging import XiansLogger

    logger = XiansLogger.for_type(MyActivity)
    logger.info("Fetched 4 sources")
    logger.error("Something broke", exc_info=True)
"""

from __future__ import annotations

import logging

from .api_handler import ApiLogHandler

_loggers: dict[str, logging.Logger] = {}
_api_handler_installed = False


def _ensure_api_handler() -> None:
    """Attach the ApiLogHandler to the root ``xians`` logger once.

    This means *all* loggers under the ``xians`` namespace will have their
    records forwarded to the server (subject to the server-level filter
    inside the handler).
    """
    global _api_handler_installed
    if _api_handler_installed:
        return

    root = logging.getLogger("xians")
    if not any(isinstance(h, ApiLogHandler) for h in root.handlers):
        root.addHandler(ApiLogHandler())
    _api_handler_installed = True


class XiansLogger:
    """Factory for obtaining context-aware loggers.

    Mirrors C# ``XiansLogger.For(type)`` / ``XiansLogger.GetLogger<T>()``.
    Returns a standard ``logging.Logger`` that:

    * Outputs to the console handler already configured by ``configure_logging``
    * Forwards records to the Xians server (via ``ApiLogHandler``) when
      ``LoggingServices`` has been initialized with a server log level.
    """

    @staticmethod
    def for_type(cls_or_name: type | str) -> logging.Logger:
        """Create or retrieve a cached logger.

        Args:
            cls_or_name: A class whose ``__qualname__`` or ``__module__`` is
                used as the logger name, or a plain string name.

        Returns:
            A standard ``logging.Logger``.
        """
        if isinstance(cls_or_name, str):
            name = cls_or_name
        else:
            name = f"{cls_or_name.__module__}.{cls_or_name.__qualname__}"

        if name in _loggers:
            return _loggers[name]

        _ensure_api_handler()
        lgr = logging.getLogger(name)
        _loggers[name] = lgr
        return lgr

    @staticmethod
    def get_logger(cls_or_name: type | str) -> logging.Logger:
        """Alias for ``for_type`` — matches C# ``XiansLogger.GetLogger<T>()``."""
        return XiansLogger.for_type(cls_or_name)

    @staticmethod
    def for_ilogger(type_: type) -> logging.Logger:
        """Alias matching C# ``XiansLogger.ForILogger(Type)``."""
        return XiansLogger.for_type(type_)


def install_api_handler_on_root() -> None:
    """Attach the ``ApiLogHandler`` to the *root* logger so that every logger
    in the application (not just ``xians.*``) forwards records to the server.

    Call this during platform initialization when server logging is enabled.
    """
    root = logging.getLogger()
    if not any(isinstance(h, ApiLogHandler) for h in root.handlers):
        root.addHandler(ApiLogHandler())
