"""Workflow logs feature — mirrors C# Xians.Lib.Logging namespace.

Public surface::

    # User-facing logger (primary API — mirrors C# Logger<T> / XiansLogger)
    from xians.agents.workflow_logs import XiansLogger

    # Background log processor (mirrors C# LoggingServices)
    from xians.agents.workflow_logs import LoggingServices

    # Centralized log-level config (mirrors C# LoggerFactory)
    from xians.agents.workflow_logs import logger_factory

    # Per-activity emitter (still available for explicit batching)
    from xians.agents.workflow_logs import WorkflowLogEmitter

    # HTTP transport
    from xians.agents.workflow_logs import WorkflowLogService

    # Models
    from xians.agents.workflow_logs import WorkflowLogLevelName, WorkflowLogRequest
"""

from .api_logger_handler import ApiLoggerHandler
from .log_emitter import WorkflowLogEmitter
from .log_service import WorkflowLogService
from .logging_services import LoggingServices
from .models import WorkflowLogLevelName, WorkflowLogRequest
from .xians_logger import XiansLogger

__all__ = [
    # Primary user-facing API
    "XiansLogger",
    # Global background processor
    "LoggingServices",
    # Python logging.Handler for server ingestion
    "ApiLoggerHandler",
    # Per-activity emitter (backward compat)
    "WorkflowLogEmitter",
    # HTTP transport layer
    "WorkflowLogService",
    # Models
    "WorkflowLogLevelName",
    "WorkflowLogRequest",
]
