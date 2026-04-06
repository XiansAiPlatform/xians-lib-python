"""Xians Logging — context-aware logging with server upload.

Matches C# Xians.Lib.Logging namespace.

Quickstart::

    from xians.logging import XiansLogger

    logger = XiansLogger.for_type(MyActivity)
    logger.info("Processing complete")
"""

from .api_handler import ApiLogHandler
from .logging_services import LoggingServices, enqueue_log, get_logging_stats
from .models.log import Log
from .xians_logger import XiansLogger, install_api_handler_on_root

__all__ = [
    "ApiLogHandler",
    "Log",
    "LoggingServices",
    "XiansLogger",
    "enqueue_log",
    "get_logging_stats",
    "install_api_handler_on_root",
]
