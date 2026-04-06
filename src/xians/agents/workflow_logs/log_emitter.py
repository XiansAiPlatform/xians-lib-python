"""Workflow log emitter — per-activity convenience wrapper.

The emitter batches log records within a single activity execution and flushes
them either when the batch-size threshold is reached, the time interval expires,
or ``flush()`` is called explicitly (typically in a ``finally`` block).

Records are uploaded via the injected ``WorkflowLogService`` **and** enqueued
to the global ``LoggingServices`` queue (when initialised) so the background
processor can capture any stragglers.

Mirrors the per-instance buffering in the previous Python implementation while
integrating with the new ``LoggingServices`` global pipeline from C#.
"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timezone

from .log_service import WorkflowLogService
from .logging_services import LoggingServices
from .models import WorkflowLogLevelName, WorkflowLogRequest
from .trace_utils import current_trace_context

logger = logging.getLogger(__name__)


class WorkflowLogEmitter:
    """Per-activity log emitter with local buffering and batch upload.

    Each ``MessageActivities.process_and_send_message`` invocation creates its
    own emitter so buffers are isolated across concurrent activities.
    """

    def __init__(
        self,
        *,
        log_service: WorkflowLogService,
        agent: str,
        workflow_type: str,
        workflow_id: str,
        workflow_run_id: str | None,
        activation: str | None,
        participant_id: str | None,
        tenant_id: str | None,
        batch_size: int = 100,
        flush_interval_seconds: float = 60.0,
    ) -> None:
        self._log_service = log_service
        self._buffer: list[WorkflowLogRequest] = []

        self._agent = agent
        self._workflow_type = workflow_type
        self._workflow_id = workflow_id
        self._workflow_run_id = workflow_run_id
        self._activation = activation
        self._participant_id = participant_id
        self._tenant_id = tenant_id

        self._batch_size = batch_size
        self._flush_interval_seconds = flush_interval_seconds
        self._last_flush_monotonic = time.monotonic()

    def _should_flush_by_time(self) -> bool:
        return (time.monotonic() - self._last_flush_monotonic) >= self._flush_interval_seconds

    async def emit(
        self,
        *,
        level: WorkflowLogLevelName,
        message: str,
        exception: str | None = None,
    ) -> None:
        """Enqueue a log record and flush if thresholds are met."""
        if not self._log_service.is_enabled_for(level):
            return

        trace_id, span_id = current_trace_context()
        record = WorkflowLogRequest(
            message=message,
            level=level,
            workflow_id=self._workflow_id,
            agent=self._agent,
            workflow_type=self._workflow_type,
            workflow_run_id=self._workflow_run_id,
            activation=self._activation,
            participant_id=self._participant_id,
            tenant_id=self._tenant_id,
            trace_id=trace_id,
            span_id=span_id,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            exception=exception,
        )
        self._buffer.append(record)

        if len(self._buffer) >= self._batch_size or self._should_flush_by_time():
            await self.flush()

    # ------------------------------------------------------------------
    # Convenience methods (mirrors C# IXiansLogger level helpers)
    # ------------------------------------------------------------------

    async def emit_trace(self, message: str) -> None:
        await self.emit(level=WorkflowLogLevelName.Trace, message=message)

    async def emit_debug(self, message: str) -> None:
        await self.emit(level=WorkflowLogLevelName.Debug, message=message)

    async def emit_info(self, message: str) -> None:
        await self.emit(level=WorkflowLogLevelName.Information, message=message)

    async def emit_warning(self, message: str) -> None:
        await self.emit(level=WorkflowLogLevelName.Warning, message=message)

    async def emit_error(self, message: str, exc: BaseException | str | None = None) -> None:
        exception_text: str | None = None
        if exc is None:
            exception_text = None
        elif isinstance(exc, str):
            exception_text = exc
        else:
            exception_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        await self.emit(level=WorkflowLogLevelName.Error, message=message, exception=exception_text)

    async def emit_critical(self, message: str, exc: BaseException | str | None = None) -> None:
        exception_text: str | None = None
        if exc is None:
            exception_text = None
        elif isinstance(exc, str):
            exception_text = exc
        else:
            exception_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        await self.emit(level=WorkflowLogLevelName.Critical, message=message, exception=exception_text)

    async def flush(self) -> None:
        """Flush buffered logs: direct upload via ``WorkflowLogService`` *and*
        enqueue to global ``LoggingServices`` for any that fail to upload directly.
        """
        if not self._buffer:
            return

        to_upload = self._buffer
        self._buffer = []
        self._last_flush_monotonic = time.monotonic()

        try:
            await self._log_service.upload_batch_async(to_upload)
        except Exception:
            logger.warning("WorkflowLogEmitter flush failed — routing to global queue", exc_info=True)
            if LoggingServices.is_initialized():
                for record in to_upload:
                    LoggingServices.enqueue_log(record)


__all__ = ["WorkflowLogEmitter"]
