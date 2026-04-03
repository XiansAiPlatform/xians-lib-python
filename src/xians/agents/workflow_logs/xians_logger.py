"""Context-aware logger — mirrors C# ``Logger<T>`` / ``XiansLogger<T>``.

``XiansLogger`` is the primary user-facing logging API for the Python SDK.
It wraps Python's ``logging.Logger`` and adds:

* **Automatic context capture** — ``XiansContext`` fields (WorkflowId, Agent, …)
  are attached via the ``ApiLoggerHandler`` (server) and structured in console output.
* **Workflow-safe routing** — inside Temporal workflows, logs are forwarded to
  ``workflow.logger`` (replay-safe); optionally dual-logged to the standard logger
  for console+server visibility (controlled by ``WORKFLOW_LOG_TO_CONSOLE``).
* **Instance caching** — ``XiansLogger.for_type(MyClass)`` returns the same
  instance on repeated calls, matching the C# ``ConcurrentDictionary`` pattern.

Quick start::

    from xians.agents.workflow_logs import XiansLogger

    logger = XiansLogger.for_name(__name__)
    logger.log_info("Processing started")
    logger.log_error("Something failed", exc=some_exception)
"""

from __future__ import annotations

import logging
import threading
import traceback
from typing import Type

from .logger_factory import should_log_workflow_to_console

__all__ = ["XiansLogger"]


class XiansLogger:
    """Unified Xians logger — mirrors ``Logger<T>`` / ``XiansLogger<T>`` from C#.

    Instances are cached per type or name (thread-safe) to match the C# pattern
    where ``Logger<T>.For()`` returns the same instance on each call.
    """

    _cache: dict[str, "XiansLogger"] = {}
    _lock = threading.Lock()

    def __init__(self, name: str) -> None:
        self._name = name
        self._logger = logging.getLogger(name)

    # ------------------------------------------------------------------
    # Factory methods (mirrors C# Logger<T>.For() / Logger.For(Type))
    # ------------------------------------------------------------------

    @classmethod
    def for_type(cls, type_: Type) -> "XiansLogger":
        """Get or create a logger for a class type (mirrors ``Logger<T>.For()``)."""
        key = f"{type_.__module__}.{type_.__qualname__}"
        return cls._get_or_create(key)

    @classmethod
    def for_name(cls, name: str) -> "XiansLogger":
        """Get or create a logger by name (e.g. ``__name__``)."""
        return cls._get_or_create(name)

    @classmethod
    def _get_or_create(cls, key: str) -> "XiansLogger":
        instance = cls._cache.get(key)
        if instance is not None:
            return instance
        with cls._lock:
            instance = cls._cache.get(key)
            if instance is not None:
                return instance
            instance = cls(key)
            cls._cache[key] = instance
            return instance

    # ------------------------------------------------------------------
    # Convenience log methods (mirrors C# IXiansLogger)
    # ------------------------------------------------------------------

    def log_trace(self, message: str) -> None:
        self._log(logging.DEBUG - 5, message)

    def log_debug(self, message: str) -> None:
        self._log(logging.DEBUG, message)

    def log_info(self, message: str) -> None:
        self._log(logging.INFO, message)

    def log_information(self, message: str) -> None:
        """Alias for ``log_info`` — mirrors C# ``LogInformation``."""
        self._log(logging.INFO, message)

    def log_warning(self, message: str) -> None:
        self._log(logging.WARNING, message)

    def log_error(self, message: str, exc: BaseException | None = None) -> None:
        self._log(logging.ERROR, message, exc=exc)

    def log_critical(self, message: str, exc: BaseException | None = None) -> None:
        self._log(logging.CRITICAL, message, exc=exc)

    # ------------------------------------------------------------------
    # Core logging method (mirrors C# Logger<T>.Log)
    # ------------------------------------------------------------------

    def _log(self, level: int, message: str, *, exc: BaseException | None = None) -> None:
        """Route the log through Workflow.Logger when in workflow, else standard logger.

        Mirrors C# ``Logger<T>.Log()`` with dual-logging for workflow context.
        """
        if self._in_workflow():
            self._log_to_workflow_logger(level, message, exc)
            if should_log_workflow_to_console():
                self._log_to_standard_logger(level, message, exc)
            return

        self._log_to_standard_logger(level, message, exc)

    def _log_to_workflow_logger(self, level: int, message: str, exc: BaseException | None) -> None:
        """Forward to ``workflow.logger`` (replay-safe). Mirrors C# ``LogToWorkflowLogger``."""
        try:
            from temporalio import workflow as _wf

            full_message = message
            if exc is not None:
                full_message = f"{message} Exception: {''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"

            wf_logger = _wf.logger
            if level >= logging.CRITICAL:
                wf_logger.critical(full_message)
            elif level >= logging.ERROR:
                wf_logger.error(full_message)
            elif level >= logging.WARNING:
                wf_logger.warning(full_message)
            elif level >= logging.INFO:
                wf_logger.info(full_message)
            elif level >= logging.DEBUG:
                wf_logger.debug(full_message)
            else:
                wf_logger.debug(full_message)
        except Exception:
            pass

    def _log_to_standard_logger(self, level: int, message: str, exc: BaseException | None) -> None:
        """Standard Python logger (console + ApiLoggerHandler → server).

        Mirrors C# ``LogToStandardLogger``.
        """
        if exc is not None:
            self._logger.log(level, message, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            self._logger.log(level, message)

    # ------------------------------------------------------------------
    # Context detection (mirrors C# IsInWorkflow)
    # ------------------------------------------------------------------

    @staticmethod
    def _in_workflow() -> bool:
        try:
            from temporalio.workflow import in_workflow
            return in_workflow()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Underlying Python logger (for advanced usage / interop)
    # ------------------------------------------------------------------

    @property
    def inner(self) -> logging.Logger:
        """Access the underlying ``logging.Logger`` for interop."""
        return self._logger

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the logger cache (use in test teardown)."""
        with cls._lock:
            cls._cache.clear()
