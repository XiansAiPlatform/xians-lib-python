"""Python logging.Handler that sends log records to the Xians server.

Matches C# ApiLogger / ApiLoggerProvider — creates Log model entries and
enqueues them for batch upload via LoggingServices.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from typing import Optional

from ..agents.core.xians_context import XiansContext
from .logging_services import LoggingServices
from .models.log import Log

_LEVEL_MAP: dict[int, str] = {
    logging.DEBUG: "Debug",
    logging.INFO: "Information",
    logging.WARNING: "Warning",
    logging.ERROR: "Error",
    logging.CRITICAL: "Critical",
}


def _python_level_to_server(level: int) -> str:
    """Map Python logging level to the C# LogLevel name expected by the server."""
    if level <= logging.DEBUG:
        return "Debug"
    return _LEVEL_MAP.get(level, "Information")


class ApiLogHandler(logging.Handler):
    """Handler that intercepts log records and forwards them to LoggingServices.

    Respects the server log level configured in LoggingServices — records below
    that threshold are silently ignored (they still reach the console handler).
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        svc = LoggingServices.get_instance()
        if not svc.is_initialized:
            return

        if record.levelno < svc._server_log_level:
            return

        try:
            message = self.format(record) if self.formatter else record.getMessage()

            exc_text: Optional[str] = None
            if record.exc_info and record.exc_info[1] is not None:
                exc_text = "".join(traceback.format_exception(*record.exc_info))

            workflow_id = XiansContext.safe_workflow_id() or "startup-context"
            workflow_run_id = _safe_get("workflow_run_id")
            agent = XiansContext.safe_agent_name() or ""
            participant_id = XiansContext.safe_participant_id()
            id_postfix = XiansContext.safe_id_postfix()
            workflow_type = XiansContext.safe_workflow_type()
            tenant_id = XiansContext.safe_tenant_id()

            log_entry = Log(
                id=str(uuid.uuid4()),
                level=_python_level_to_server(record.levelno),
                message=message,
                workflowId=workflow_id,
                workflowRunId=workflow_run_id,
                workflowType=workflow_type,
                agent=agent,
                activation=id_postfix,
                participantId=participant_id,
                tenantId=tenant_id,
                exception=exc_text,
            )

            svc.enqueue_log(log_entry)

        except Exception:
            self.handleError(record)


def _safe_get(attr: str) -> Optional[str]:
    """Best-effort extraction from Temporal context."""
    try:
        return XiansContext._get_from_temporal_context(attr)
    except Exception:
        return None
