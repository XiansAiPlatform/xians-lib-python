"""Xians Logging — context-aware logging with server upload.

Matches C# Xians.Lib.Logging namespace.

Quickstart::

    from xians.logging import XiansLogger

    logger = XiansLogger.for_type(MyActivity)
    logger.trace("Low-level detail")
    logger.info("Processing complete")
"""

# Register TRACE level before any logger is created.
from .trace_level import TRACE, register_trace_level

register_trace_level()

from .api_handler import ApiLogHandler
from .logging_services import LoggingServices, enqueue_log, get_logging_stats
from .models.log import Log
from .xians_logger import XiansLogger, install_api_handler_on_root

__all__ = [
    "TRACE",
    "ApiLogHandler",
    "Log",
    "LoggingServices",
    "XiansLogger",
    "enqueue_log",
    "get_logging_stats",
    "install_api_handler_on_root",
]
