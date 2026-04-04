"""Python ``logging.Handler`` that feeds into ``LoggingServices`` — mirrors C# ApiLoggerProvider + ApiLogger.

Attach this handler to any Python logger (or the root logger) and every log
record whose level meets the configured server threshold is converted to a
``WorkflowLogRequest``, enriched with ``XiansContext`` correlation fields, and
enqueued to the global ``LoggingServices`` queue for background batch upload.

Temporal message processing:
  Certain Temporal-internal messages are re-classified (e.g. ActivityFailureException
  → Critical) to match the C# ``ApiLogger.ProcessTemporalMessage`` behaviour.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .logger_factory import get_server_log_level
from .logging_services import LoggingServices
from .models import WorkflowLogLevelName, WorkflowLogRequest

__all__ = ["ApiLoggerHandler"]


def _python_level_to_workflow(level: int) -> WorkflowLogLevelName:
    """Map a Python logging level to the nearest ``WorkflowLogLevelName``."""
    if level >= logging.CRITICAL:
        return WorkflowLogLevelName.Critical
    if level >= logging.ERROR:
        return WorkflowLogLevelName.Error
    if level >= logging.WARNING:
        return WorkflowLogLevelName.Warning
    if level >= logging.INFO:
        return WorkflowLogLevelName.Information
    if level >= logging.DEBUG:
        return WorkflowLogLevelName.Debug
    return WorkflowLogLevelName.Trace


def _process_temporal_message(message: str, level: int) -> int:
    """Re-classify Temporal internal messages — mirrors C# ``ApiLogger.ProcessTemporalMessage``.

    Returns the (possibly adjusted) Python log level.
    """
    if level >= logging.ERROR and "ActivityFailureException" in message:
        return logging.CRITICAL

    if level <= logging.DEBUG and "Activity task failed" in message:
        return logging.CRITICAL

    if level > logging.DEBUG:
        return level

    if "Sending activity completion" not in message:
        return level

    if level <= logging.DEBUG and '"failed"' in message:
        return logging.ERROR

    return level


def _current_trace_context() -> tuple[str | None, str | None]:
    """Extract OpenTelemetry trace/span IDs when instrumentation is active."""
    try:
        from opentelemetry import trace as otel_trace  # type: ignore

        span = otel_trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is None or not getattr(ctx, "is_valid", False):
            return None, None
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        return None, None


class ApiLoggerHandler(logging.Handler):
    """Python logging handler that mirrors C# ``ApiLoggerProvider / ApiLogger``.

    Reads correlation data from ``XiansContext`` at emit-time so each log
    record contains the correct workflow/activity context, then enqueues the
    record to ``LoggingServices`` for background batch upload.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)

    # ------------------------------------------------------------------
    # logging.Handler interface
    # ------------------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        try:
            server_level = get_server_log_level()
            if record.levelno < server_level:
                return

            effective_level = _process_temporal_message(record.getMessage(), record.levelno)
            if effective_level < server_level:
                return

            self._enqueue(record, effective_level)
        except Exception:
            self.handleError(record)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enqueue(self, record: logging.LogRecord, effective_level: int) -> None:
        from ...agents.core.xians_context import XiansContext

        workflow_id = XiansContext.safe_workflow_id() or "startup-context"
        workflow_run_id = XiansContext._get_from_temporal_context("run_id")
        workflow_type = XiansContext.safe_workflow_type()
        agent = XiansContext.safe_agent_name() or ""
        participant_id = XiansContext.safe_participant_id()
        id_postfix = XiansContext.safe_id_postfix()
        tenant_id = XiansContext.safe_tenant_id()

        trace_id, span_id = _current_trace_context()

        exception_text: str | None = None
        if record.exc_info and record.exc_info[1] is not None:
            exception_text = self.format(record) if record.exc_text is None else record.exc_text

        # Use Workflow.NewGuid inside workflow for determinism (mirror C#);
        # fall back to uuid4 outside workflow.
        try:
            from temporalio.workflow import in_workflow, unsafe

            if in_workflow():
                log_id = str(unsafe.new_guid())
            else:
                log_id = str(uuid.uuid4())
        except Exception:
            log_id = str(uuid.uuid4())

        log_record = WorkflowLogRequest(
            message=record.getMessage(),
            level=_python_level_to_workflow(effective_level),
            workflow_id=workflow_id,
            agent=agent or "unknown",
            workflow_type=workflow_type,
            workflow_run_id=workflow_run_id,
            activation=id_postfix,
            participant_id=participant_id,
            tenant_id=tenant_id,
            trace_id=trace_id,
            span_id=span_id,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            exception=exception_text,
        )

        LoggingServices.enqueue_log(log_record)
