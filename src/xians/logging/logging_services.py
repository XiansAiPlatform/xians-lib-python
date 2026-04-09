"""Background log processor and batch uploader. Matches C# LoggingServices.

Manages an in-memory queue of Log entries and uploads them in periodic batches
to the Xians server via ``POST /api/agent/logs``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from typing import Any, Optional

import httpx

from ..constants.v1.core import XIANS_API_LOGS
from .models.log import Log

_stdlib_logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


class LoggingServices:
    """Singleton-style service that queues logs and uploads them in batches.

    Lifecycle:
        1. ``initialize(http_client)`` — called once during platform startup
        2. Logs are enqueued via ``enqueue_log(log)``
        3. A background thread periodically uploads batches
        4. ``shutdown()`` — flushes remaining logs and stops the thread

    The background thread creates its own ``httpx.AsyncClient`` so it has a
    dedicated asyncio event loop and connection pool.  This avoids the
    "bound to a different event loop" ``RuntimeError`` that occurs when an
    ``AsyncClient`` created on the main loop is reused from a second loop.
    """

    _instance: Optional[LoggingServices] = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._queue: deque[Log] = deque()
        self._queue_lock = threading.Lock()
        self._http_client_kwargs: dict[str, Any] = {}
        self._is_initialized = False
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._batch_size = 100
        self._processing_interval_s = 30.0
        self._retry_counts: dict[str, int] = {}
        self._verbose_diagnostics = False
        self._first_log_enqueued = False
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._server_log_level: int = logging.WARNING

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> LoggingServices:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = LoggingServices()
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    def initialize(
        self,
        http_client: httpx.AsyncClient,
        server_log_level: int = logging.WARNING,
    ) -> None:
        """Start the background log processor.

        Args:
            http_client: A reference ``httpx.AsyncClient`` whose base URL,
                         headers, timeout and TLS settings are copied so that
                         the background thread can create its own client on a
                         dedicated event loop.
            server_log_level: Minimum Python logging level for server upload.
                              Logs below this level are silently discarded.
        """
        if self._is_initialized:
            if self._verbose_diagnostics:
                print("[LoggingServices] Already initialized, skipping")
            return

        self._http_client_kwargs = {
            "base_url": str(http_client.base_url),
            "timeout": http_client.timeout,
            "headers": dict(http_client.headers),
        }
        self._server_log_level = server_log_level
        self._stop_event.clear()
        self._start_processor()
        self._is_initialized = True

        print(
            f"[LoggingServices] Initialized — upload interval: "
            f"{self._processing_interval_s:.0f}s, batch size: {self._batch_size}, "
            f"server log level: {logging.getLevelName(server_log_level)}"
        )

    def enqueue_log(self, log: Log) -> None:
        """Add a log entry to the upload queue. Thread-safe."""
        if not self._is_initialized:
            if self._verbose_diagnostics:
                print("[LoggingServices] WARNING: log enqueued before init")
            return

        with self._queue_lock:
            self._queue.append(log)

        if not self._first_log_enqueued:
            self._first_log_enqueued = True
            print(
                f"[LoggingServices] First log enqueued. "
                f"Logs will be uploaded every {self._processing_interval_s:.0f}s"
            )

    def configure_batch_settings(
        self,
        batch_size: int = 100,
        processing_interval_s: float = 30.0,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if processing_interval_s <= 0:
            raise ValueError("processing_interval_s must be positive")
        self._batch_size = batch_size
        self._processing_interval_s = processing_interval_s
        print(
            f"[LoggingServices] Settings updated — interval: "
            f"{processing_interval_s:.0f}s, batch size: {batch_size}"
        )

    def enable_verbose_diagnostics(self, enabled: bool = True) -> None:
        self._verbose_diagnostics = enabled
        print(f"[LoggingServices] Verbose diagnostics {'enabled' if enabled else 'disabled'}")

    def get_stats(self) -> tuple[int, int]:
        """Return ``(queued_count, retrying_count)``."""
        with self._queue_lock:
            queued = len(self._queue)
        return queued, len(self._retry_counts)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Flush remaining logs and stop the background thread."""
        print("[LoggingServices] Shutting down, flushing logs...")

        self._stop_event.set()

        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5.0)

        self._flush_remaining()

        self._is_initialized = False
        self._retry_counts.clear()
        self._first_log_enqueued = False
        print("[LoggingServices] Log flushing completed")

    # ------------------------------------------------------------------
    # Background processing
    # ------------------------------------------------------------------

    def _start_processor(self) -> None:
        if self._processing_thread and self._processing_thread.is_alive():
            return

        self._processing_thread = threading.Thread(
            target=self._process_loop,
            name="XiansLogProcessingThread",
            daemon=True,
        )
        print(
            f"[LoggingServices] Starting server log processing thread "
            f"(interval: {self._processing_interval_s:.0f}s, batch: {self._batch_size})"
        )
        self._processing_thread.start()

    def _process_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._event_loop = loop
        client = httpx.AsyncClient(**self._http_client_kwargs)
        try:
            while not self._stop_event.is_set():
                try:
                    loop.run_until_complete(self._process_batch(client))
                except Exception as exc:
                    print(f"[LoggingServices] Error in processing thread: {exc}")
                self._stop_event.wait(self._processing_interval_s)
        finally:
            loop.run_until_complete(client.aclose())
            loop.close()
            self._event_loop = None

    async def _process_batch(self, client: httpx.AsyncClient) -> None:
        with self._queue_lock:
            if not self._queue:
                if self._verbose_diagnostics:
                    print("[LoggingServices] Queue empty, nothing to process")
                return

            batch: list[Log] = []
            while self._queue and len(batch) < self._batch_size:
                batch.append(self._queue.popleft())

        if not batch:
            return

        remaining = len(self._queue)
        print(
            f"[LoggingServices] Uploading batch of {len(batch)} logs, "
            f"{remaining} remaining in queue"
        )
        await self._send_batch(client, batch)

    async def _send_batch(self, client: httpx.AsyncClient, logs: list[Log]) -> None:
        try:
            payload = [
                log.model_dump(mode="json", by_alias=True, exclude_none=True)
                for log in logs
            ]

            response = await client.post(XIANS_API_LOGS, json=payload)

            if response.is_success:
                print(f"[LoggingServices] Successfully uploaded {len(logs)} logs to server")
                for log in logs:
                    if log.id:
                        self._retry_counts.pop(log.id, None)
            else:
                body = response.text
                print(
                    f"[LoggingServices] ERROR: API responded {response.status_code}"
                )
                if self._verbose_diagnostics:
                    print(f"[LoggingServices] Response: {body}")
                self._requeue(logs)

        except httpx.HTTPError as exc:
            print(f"[LoggingServices] ERROR: HTTP exception: {exc}")
            self._requeue(logs)
        except Exception as exc:
            print(f"[LoggingServices] ERROR: Unexpected: {exc}")
            self._requeue(logs)

    def _requeue(self, logs: list[Log]) -> None:
        with self._queue_lock:
            for log in logs:
                log_id = log.id or ""
                if not log_id:
                    self._queue.append(log)
                    continue
                count = self._retry_counts.get(log_id, 0)
                if count < _MAX_RETRIES:
                    self._retry_counts[log_id] = count + 1
                    self._queue.append(log)
                else:
                    self._retry_counts.pop(log_id, None)
                    print(
                        f"[LoggingServices] Dropping log {log_id} after "
                        f"{_MAX_RETRIES} failed attempts"
                    )

    def _flush_remaining(self) -> None:
        """Synchronously flush all queued logs on shutdown."""
        loop = asyncio.new_event_loop()
        client = httpx.AsyncClient(**self._http_client_kwargs)
        try:
            while True:
                with self._queue_lock:
                    if not self._queue:
                        break
                loop.run_until_complete(self._process_batch(client))
        except Exception as exc:
            print(f"[LoggingServices] Error during flush: {exc}")
        finally:
            loop.run_until_complete(client.aclose())
            loop.close()


# Module-level convenience functions mirroring C# static API
def enqueue_log(log: Log) -> None:
    LoggingServices.get_instance().enqueue_log(log)


def get_logging_stats() -> tuple[int, int]:
    return LoggingServices.get_instance().get_stats()
