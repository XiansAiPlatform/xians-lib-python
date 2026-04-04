"""Global log queue and background processor — mirrors C# LoggingServices.

Responsibilities:
- Global thread-safe queue for all ``WorkflowLogRequest`` records
- Background daemon thread that batches and uploads logs at a configurable interval
- Retry tracking per log (drop after ``MAX_RETRIES``) to prevent infinite accumulation
- Clean shutdown: cancel background thread, flush remaining logs

Usage::

    LoggingServices.initialize(workflow_log_service)
    LoggingServices.enqueue_log(record)
    # ... at shutdown ...
    LoggingServices.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import queue
import sys
import threading
import time
import uuid
from typing import TYPE_CHECKING

from .constants import DEFAULT_BATCH_SIZE, DEFAULT_PROCESSING_INTERVAL_SECONDS, MAX_RETRIES
from .models import WorkflowLogRequest

if TYPE_CHECKING:
    from .log_service import WorkflowLogService

_logger = logging.getLogger(__name__)

__all__ = ["LoggingServices"]


class LoggingServices:
    """Static (class-level) logging service — mirrors C# ``LoggingServices``.

    All methods are class methods operating on class-level state so that the
    global singleton pattern matches the C# ``static class LoggingServices``.
    """

    _global_log_queue: queue.Queue[WorkflowLogRequest] = queue.Queue()
    _processing_lock = threading.Lock()
    _processing_thread: threading.Thread | None = None
    _cancel_event = threading.Event()
    _is_initialized = False
    _init_lock = threading.Lock()

    _workflow_log_service: WorkflowLogService | None = None
    _batch_size: int = DEFAULT_BATCH_SIZE
    _processing_interval_seconds: float = DEFAULT_PROCESSING_INTERVAL_SECONDS

    _log_retry_count: dict[str, int] = {}
    _retry_lock = threading.Lock()

    _verbose_diagnostics: bool = False
    _first_log_enqueued: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._is_initialized

    @classmethod
    def enqueue_log(cls, log: WorkflowLogRequest) -> None:
        """Enqueue a log record for background upload.

        No-op when the service has not been initialized (mirrors C#).
        """
        if not cls._is_initialized:
            if cls._verbose_diagnostics:
                print("[LoggingServices] WARNING: enqueue before init", file=sys.stderr)
            return

        cls._global_log_queue.put_nowait(log)

        if not cls._first_log_enqueued:
            cls._first_log_enqueued = True
            print(
                f"[LoggingServices] First log enqueued. "
                f"Logs will be uploaded every {cls._processing_interval_seconds:.0f}s"
            )
        elif cls._verbose_diagnostics:
            print(f"[LoggingServices] Log enqueued. Queue size: ~{cls._global_log_queue.qsize()}")

    @classmethod
    def initialize(cls, workflow_log_service: WorkflowLogService) -> None:
        """Initialize the global log processor and start the background thread.

        Mirrors C# ``LoggingServices.Initialize(IHttpClientService)``.
        """
        if cls._is_initialized:
            return

        with cls._init_lock:
            if cls._is_initialized:
                return

            if workflow_log_service is None:
                raise ValueError("workflow_log_service is required")

            cls._workflow_log_service = workflow_log_service
            cls._start_log_processor()
            cls._is_initialized = True

            print(
                f"[LoggingServices] Initialized — upload interval: "
                f"{cls._processing_interval_seconds:.0f}s, batch size: {cls._batch_size}"
            )

    @classmethod
    def shutdown(cls) -> None:
        """Stop the background thread and flush remaining logs.

        Mirrors C# ``LoggingServices.OnApplicationShutdown() / Shutdown()``.
        """
        print("[LoggingServices] Shutting down, flushing logs…")

        with cls._processing_lock:
            cls._cancel_event.set()
            if cls._processing_thread is not None and cls._processing_thread.is_alive():
                cls._processing_thread.join(timeout=5.0)
                if cls._processing_thread.is_alive():
                    print("[LoggingServices] Background thread did not stop within timeout")

        # Flush any remaining logs synchronously
        while not cls._global_log_queue.empty():
            cls._process_log_batch_sync()
            time.sleep(0.1)

        with cls._init_lock:
            cls._is_initialized = False

        with cls._retry_lock:
            cls._log_retry_count.clear()

        cls._first_log_enqueued = False
        print("[LoggingServices] Log flushing completed")

    @classmethod
    def configure_batch_settings(
        cls,
        batch_size: int | None = None,
        processing_interval_seconds: float | None = None,
    ) -> None:
        """Adjust batch size and upload interval (mirrors C# ``ConfigureBatchSettings``)."""
        if batch_size is not None:
            if batch_size <= 0:
                raise ValueError("batch_size must be positive")
            cls._batch_size = batch_size
        if processing_interval_seconds is not None:
            if processing_interval_seconds <= 0:
                raise ValueError("processing_interval_seconds must be positive")
            cls._processing_interval_seconds = processing_interval_seconds

    @classmethod
    def enable_verbose_diagnostics(cls, enabled: bool = True) -> None:
        cls._verbose_diagnostics = enabled

    @classmethod
    def get_logging_stats(cls) -> tuple[int, int]:
        """Return ``(queued_count, retrying_count)`` — mirrors C# ``GetLoggingStats``."""
        with cls._retry_lock:
            retrying = len(cls._log_retry_count)
        return cls._global_log_queue.qsize(), retrying

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    @classmethod
    def _start_log_processor(cls) -> None:
        with cls._processing_lock:
            if cls._processing_thread is not None and cls._processing_thread.is_alive():
                return

            cls._cancel_event.clear()
            cls._processing_thread = threading.Thread(
                target=cls._process_logs_thread,
                name="LogProcessingThread",
                daemon=True,
            )
            cls._processing_thread.start()

    @classmethod
    def _process_logs_thread(cls) -> None:
        """Runs in a daemon thread; wakes every ``_processing_interval_seconds``."""
        loop = asyncio.new_event_loop()
        try:
            while not cls._cancel_event.is_set():
                try:
                    cls._process_log_batch(loop)
                except Exception as exc:
                    print(f"[LoggingServices] Error in processing thread: {exc}", file=sys.stderr)
                    time.sleep(10)

                cls._cancel_event.wait(timeout=cls._processing_interval_seconds)
        finally:
            loop.close()

    @classmethod
    def _process_log_batch(cls, loop: asyncio.AbstractEventLoop) -> None:
        if cls._global_log_queue.empty():
            return

        if cls._workflow_log_service is None:
            print("[LoggingServices] WARNING: no workflow_log_service, cannot upload", file=sys.stderr)
            return

        batch: list[WorkflowLogRequest] = []
        while len(batch) < cls._batch_size:
            try:
                batch.append(cls._global_log_queue.get_nowait())
            except queue.Empty:
                break

        if not batch:
            return

        remaining = cls._global_log_queue.qsize()
        print(f"[LoggingServices] Uploading batch of {len(batch)} logs, ~{remaining} remaining")

        try:
            loop.run_until_complete(cls._workflow_log_service.upload_batch_async(batch))
            print(f"[LoggingServices] ✓ Successfully uploaded {len(batch)} logs")
            cls._clear_retry_tracking(batch)
        except Exception as exc:
            print(f"[LoggingServices] ERROR: upload failed: {exc}", file=sys.stderr)
            cls._requeue_batch(batch)

    @classmethod
    def _process_log_batch_sync(cls) -> None:
        """Synchronous batch flush used during shutdown."""
        loop = asyncio.new_event_loop()
        try:
            cls._process_log_batch(loop)
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Retry helpers (mirrors C# RequeueLogBatch + retry tracking)
    # ------------------------------------------------------------------

    @classmethod
    def _requeue_batch(cls, batch: list[WorkflowLogRequest]) -> None:
        with cls._retry_lock:
            for log in batch:
                log_id = getattr(log, "_tracking_id", None) or str(uuid.uuid4())
                if not hasattr(log, "_tracking_id"):
                    object.__setattr__(log, "_tracking_id", log_id)

                count = cls._log_retry_count.get(log_id, 0)
                if count < MAX_RETRIES:
                    cls._log_retry_count[log_id] = count + 1
                    cls._global_log_queue.put_nowait(log)
                else:
                    cls._log_retry_count.pop(log_id, None)
                    print(
                        f"[LoggingServices] Dropping log after {MAX_RETRIES} retries",
                        file=sys.stderr,
                    )

    @classmethod
    def _clear_retry_tracking(cls, batch: list[WorkflowLogRequest]) -> None:
        with cls._retry_lock:
            for log in batch:
                log_id = getattr(log, "_tracking_id", None)
                if log_id:
                    cls._log_retry_count.pop(log_id, None)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    @classmethod
    def reset_for_tests(cls) -> None:
        """Full reset (use only in test teardown)."""
        cls._cancel_event.set()
        if cls._processing_thread is not None and cls._processing_thread.is_alive():
            cls._processing_thread.join(timeout=2.0)

        # drain queue
        while not cls._global_log_queue.empty():
            try:
                cls._global_log_queue.get_nowait()
            except queue.Empty:
                break

        cls._processing_thread = None
        cls._workflow_log_service = None
        cls._is_initialized = False
        cls._first_log_enqueued = False
        cls._verbose_diagnostics = False
        cls._batch_size = DEFAULT_BATCH_SIZE
        cls._processing_interval_seconds = DEFAULT_PROCESSING_INTERVAL_SECONDS
        with cls._retry_lock:
            cls._log_retry_count.clear()
