"""Context-aware logger — mirrors C# ``Logger<T>`` / ``XiansLogger<T>``.

``XiansLogger`` is the primary user-facing logging API for the Python SDK.
It wraps Python's ``logging.Logger`` and adds:

* **Automatic context capture** — ``XiansContext`` fields (WorkflowId, Agent, …)
  are attached to every log record via ``extra`` dict (mirrors C# ``BeginScope``).
* **Workflow-safe routing** — inside Temporal workflows, logs are forwarded to
  ``workflow.logger`` (replay-safe); optionally dual-logged to the standard logger
  for console+server visibility (controlled by ``WORKFLOW_LOG_TO_CONSOLE``).
* **Instance caching** — ``XiansLogger.for_type(MyClass)`` returns the same
  instance on repeated calls, matching the C# ``ConcurrentDictionary`` pattern.
* **Lazy logger init** — underlying ``logging.Logger`` is created on first use
  (mirrors C# ``Lazy<ILogger>``).

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
from typing import Optional, Type

from .logger_factory import should_log_workflow_to_console

__all__ = ["XiansLogger"]


class XiansLogger:
    """Unified Xians logger — mirrors ``Logger<T>`` / ``XiansLogger<T>`` from C#.

    Instances are cached per type or name (thread-safe) to match the C# pattern
    where ``Logger<T>.For()`` / ``XiansLogger.For(type)`` returns the same
    instance on each call via ``ConcurrentDictionary``.
    """

    _cache: dict[str, "XiansLogger"] = {}
    _lock = threading.Lock()

    def __init__(self, name: str) -> None:
        self._name = name
        self._logger: logging.Logger | None = None

    # ------------------------------------------------------------------
    # Lazy logger init (mirrors C# Lazy<ILogger>)
    # ------------------------------------------------------------------

    def _get_logger(self) -> logging.Logger:
        """Lazy-create the underlying ``logging.Logger`` on first use.

        Mirrors C# ``Lazy<ILogger>`` in ``Logger<T>`` / ``TypeBasedLoggerWrapper``.
        """
        if self._logger is None:
            self._logger = logging.getLogger(self._name)
        return self._logger

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
    # Convenience log methods (mirrors C# IXiansLogger interface)
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

    def is_enabled(self, level: int) -> bool:
        """Check if the given level is enabled. Mirrors C# ``ILogger.IsEnabled``."""
        return self._get_logger().isEnabledFor(level)

    # ------------------------------------------------------------------
    # Context data (mirrors C# GetContextData())
    # ------------------------------------------------------------------

    @staticmethod
    def _get_context_data() -> Optional[dict[str, object]]:
        """Build workflow context dict for log scoping.

        Mirrors C# ``Logger<T>.GetContextData()`` / ``TypeBasedLoggerWrapper.GetContextData()``:
        reads SafeWorkflowId, SafeWorkflowRunId, SafeWorkflowType, SafeAgentName
        from ``XiansContext`` and returns a dict (or None if not in workflow/activity).
        """
        try:
            from ...agents.core.xians_context import XiansContext

            if not XiansContext.in_workflow_or_activity():
                return None

            context_data: dict[str, object] = {}

            workflow_id = XiansContext.safe_workflow_id()
            workflow_run_id = XiansContext._get_from_temporal_context("run_id")
            workflow_type = XiansContext.safe_workflow_type()
            agent_name = XiansContext.safe_agent_name()
            participant_id = XiansContext.safe_participant_id()

            if workflow_id is not None:
                context_data["WorkflowId"] = workflow_id
            if workflow_run_id is not None:
                context_data["WorkflowRunId"] = workflow_run_id
            if workflow_type is not None:
                context_data["WorkflowType"] = workflow_type
            if agent_name is not None:
                context_data["Agent"] = agent_name
            if participant_id is not None:
                context_data["ParticipantId"] = participant_id

            return context_data if context_data else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Core logging method (mirrors C# Logger<T>.Log)
    # ------------------------------------------------------------------

    def _log(self, level: int, message: str, *, exc: BaseException | None = None) -> None:
        """Route the log through Workflow.Logger when in workflow, else standard logger.

        Mirrors C# ``Logger<T>.Log()`` exactly:
        1. Read context data (GetContextData)
        2. If in workflow: LogToWorkflowLogger + dual-log via LogToStandardLogger
        3. Else: LogToStandardLogger
        """
        context_data = self._get_context_data()

        if self._in_workflow():
            self._log_to_workflow_logger(level, message, exc, context_data)
            if should_log_workflow_to_console():
                self._log_to_standard_logger(level, message, exc, context_data)
            return

        self._log_to_standard_logger(level, message, exc, context_data)

    def _log_to_workflow_logger(
        self,
        level: int,
        message: str,
        exc: BaseException | None,
        context_data: Optional[dict[str, object]],
    ) -> None:
        """Forward to ``workflow.logger`` (replay-safe).

        Mirrors C# ``LogToWorkflowLogger``:
        - Creates scope with context data on Workflow.Logger
        - Formats exception into message
        - Routes to appropriate level method
        """
        try:
            from temporalio import workflow as _wf

            full_message = message
            if exc is not None:
                full_message = f"{message} Exception: {''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"

            wf_logger = _wf.logger

            extra = context_data if context_data else {}
            if level >= logging.CRITICAL:
                wf_logger.critical(full_message, extra=extra)
            elif level >= logging.ERROR:
                wf_logger.error(full_message, extra=extra)
            elif level >= logging.WARNING:
                wf_logger.warning(full_message, extra=extra)
            elif level >= logging.INFO:
                wf_logger.info(full_message, extra=extra)
            elif level >= logging.DEBUG:
                wf_logger.debug(full_message, extra=extra)
            else:
                wf_logger.debug(full_message, extra=extra)
        except Exception:
            pass

    def _log_to_standard_logger(
        self,
        level: int,
        message: str,
        exc: BaseException | None,
        context_data: Optional[dict[str, object]],
    ) -> None:
        """Standard Python logger (console + ApiLoggerHandler -> server).

        Mirrors C# ``LogToStandardLogger``:
        - Creates scope with context data on the standard logger
        - Logs message with optional exception info
        """
        logger = self._get_logger()
        extra = context_data if context_data else {}

        if exc is not None:
            logger.log(level, message, exc_info=(type(exc), exc, exc.__traceback__), extra=extra)
        else:
            logger.log(level, message, extra=extra)

    # ------------------------------------------------------------------
    # Context detection (mirrors C# Workflow.InWorkflow)
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
        """Access the underlying ``logging.Logger`` for interop.

        Mirrors C# ``ILogger`` — the raw logger for frameworks that need it.
        """
        return self._get_logger()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the logger cache (use in test teardown)."""
        with cls._lock:
            cls._cache.clear()
