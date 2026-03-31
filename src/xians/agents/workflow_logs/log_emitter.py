"""Workflow log emitter adapter.

Responsibilities:
- Normalize record shape to `WorkflowLogRequest`
- Map internal log calls to backend log level semantics
- Buffer and flush logs in batches
- Flush on activity completion (best-effort)
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback

from .log_service import WorkflowLogService
from .models import WorkflowLogLevelName, WorkflowLogRequest

logger = logging.getLogger(__name__)


class WorkflowLogEmitter:
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
            exception=exception,
        )
        self._buffer.append(record)

        # Flush early for large bursts; periodic flush to match platform behavior.
        if len(self._buffer) >= self._batch_size or self._should_flush_by_time():
            await self.flush()

    async def emit_info(self, message: str) -> None:
        await self.emit(level=WorkflowLogLevelName.Information, message=message)

    async def emit_debug(self, message: str) -> None:
        await self.emit(level=WorkflowLogLevelName.Debug, message=message)

    async def emit_error(self, message: str, exc: BaseException | str | None = None) -> None:
        exception_text: str | None = None
        if exc is None:
            exception_text = None
        elif isinstance(exc, str):
            exception_text = exc
        else:
            exception_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        await self.emit(level=WorkflowLogLevelName.Error, message=message, exception=exception_text)

    async def flush(self) -> None:
        """Flush buffered logs to the backend (best-effort)."""
        if not self._buffer:
            return

        to_upload = self._buffer
        self._buffer = []
        self._last_flush_monotonic = time.monotonic()

        try:
            await self._log_service.upload_batch_async(to_upload)
        except Exception:
            # Best-effort: never fail user handler due to logging.
            logger.warning("WorkflowLogEmitter flush failed", exc_info=True)


__all__ = ["WorkflowLogEmitter"]

