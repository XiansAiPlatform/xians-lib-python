"""Unit tests for workflow log ingestion payloads and the new logging subsystem.

Covers:
  - WorkflowLogRequest serialization (name vs number level format)
  - WorkflowLogService level gating + fallback negotiation
  - WorkflowLogEmitter batch-size and time-interval flush
  - Temporal workflow-id helpers in message_activity_workflow_logging
  - LoggingServices global queue + background processor
  - LoggerFactory level parsing + env-var resolution
  - ApiLoggerHandler enqueue behaviour
  - XiansLogger instance caching and level dispatch
"""

from unittest.mock import MagicMock, patch
import logging
import os

import pytest

from xians.agents.workflow_logs.log_emitter import WorkflowLogEmitter
from xians.agents.workflow_logs.log_service import WorkflowLogService
from xians.agents.workflow_logs.logging_services import LoggingServices
from xians.agents.workflow_logs.models import (
    LOG_LEVEL_NAME_TO_NUMBER,
    WorkflowLogLevelName,
    WorkflowLogRequest,
)
from xians.exceptions.v1.errors import XiansServerError


# ======================================================================
# Temporal ID helpers (message_activity_workflow_logging)
# ======================================================================

def test_temporal_workflow_id_for_logging_prefers_activity_info() -> None:
    from xians.temporal_workflows.v1.message_activity_workflow_logging import (
        temporal_workflow_id_for_logging,
    )

    info = MagicMock(workflow_id="tenant:Agent:Flow:activation-1")
    with patch(
        "xians.temporal_workflows.v1.message_activity_workflow_logging.activity.info",
        return_value=info,
    ):
        assert temporal_workflow_id_for_logging("tenant:Agent:Flow") == "tenant:Agent:Flow:activation-1"


def test_temporal_workflow_id_for_logging_falls_back_when_no_activity() -> None:
    from xians.temporal_workflows.v1.message_activity_workflow_logging import (
        temporal_workflow_id_for_logging,
    )

    with patch(
        "xians.temporal_workflows.v1.message_activity_workflow_logging.activity.info",
        side_effect=RuntimeError("not in activity"),
    ):
        assert temporal_workflow_id_for_logging("tenant:Agent:Flow") == "tenant:Agent:Flow"


def test_temporal_workflow_id_for_logging_falls_back_when_activity_id_empty() -> None:
    from xians.temporal_workflows.v1.message_activity_workflow_logging import (
        temporal_workflow_id_for_logging,
    )

    info = MagicMock(workflow_id="")
    with patch(
        "xians.temporal_workflows.v1.message_activity_workflow_logging.activity.info",
        return_value=info,
    ):
        assert temporal_workflow_id_for_logging("tenant:Agent:Flow") == "tenant:Agent:Flow"


def test_temporal_workflow_run_id_for_logging_prefers_activity_info() -> None:
    from xians.temporal_workflows.v1.message_activity_workflow_logging import (
        temporal_workflow_run_id_for_logging,
    )

    info = MagicMock(workflow_run_id="01HZ-run-from-temporal")
    with patch(
        "xians.temporal_workflows.v1.message_activity_workflow_logging.activity.info",
        return_value=info,
    ):
        assert (
            temporal_workflow_run_id_for_logging("from-request")
            == "01HZ-run-from-temporal"
        )


# ======================================================================
# WorkflowLogRequest serialization
# ======================================================================

def test_workflow_log_request_serialization_name_and_number() -> None:
    req = WorkflowLogRequest(
        message="Workflow started",
        level=WorkflowLogLevelName.Information,
        workflow_id="tenant:Agent:Flow:activation-1",
        agent="Agent",
        workflow_type="Agent:Flow",
        workflow_run_id="run-123",
        activation="activation-1",
        participant_id="user-1",
        tenant_id="tenant",
        exception=None,
    )

    payload_name = req.to_api_dict(level_format="name")
    assert payload_name["level"] == "Information"
    assert payload_name["workflowId"] == "tenant:Agent:Flow:activation-1"
    assert payload_name["agent"] == "Agent"
    assert payload_name["workflowRunId"] == "run-123"
    assert payload_name["participantId"] == "user-1"

    payload_number = req.to_api_dict(level_format="number")
    assert payload_number["level"] == LOG_LEVEL_NAME_TO_NUMBER["Information"]


# ======================================================================
# WorkflowLogService — level format fallback
# ======================================================================

@pytest.mark.asyncio
async def test_workflow_log_service_falls_back_on_level_format() -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        async def upload_agent_logs(self, payload: list[dict]) -> None:
            self.calls.append(payload)
            if payload and isinstance(payload[0].get("level"), str):
                raise XiansServerError("bad level format", status_code=400)
            return

    dummy = DummyClient()
    service = WorkflowLogService(dummy, prefer_numeric_levels=False)  # type: ignore[arg-type]

    req = WorkflowLogRequest(
        message="x",
        level=WorkflowLogLevelName.Error,
        workflow_id="tenant:Agent:Flow:activation-1",
        agent="Agent",
    )

    await service.upload_batch_async([req])

    assert len(dummy.calls) == 2
    assert dummy.calls[0][0]["level"] == "Error"
    assert dummy.calls[1][0]["level"] == LOG_LEVEL_NAME_TO_NUMBER["Error"]


@pytest.mark.asyncio
async def test_workflow_log_service_uses_sticky_numeric_after_fallback() -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        async def upload_agent_logs(self, payload: list[dict]) -> None:
            self.calls.append(payload)
            if payload and isinstance(payload[0].get("level"), str):
                raise XiansServerError("bad level format", status_code=400)

    dummy = DummyClient()
    service = WorkflowLogService(dummy, prefer_numeric_levels=False)  # type: ignore[arg-type]

    req = WorkflowLogRequest(
        message="x",
        level=WorkflowLogLevelName.Warning,
        workflow_id="tenant:Agent:Flow:activation-1",
        agent="Agent",
    )

    await service.upload_batch_async([req])
    await service.upload_batch_async([req])

    assert len(dummy.calls) == 3
    assert isinstance(dummy.calls[0][0]["level"], str)
    assert isinstance(dummy.calls[1][0]["level"], int)
    assert isinstance(dummy.calls[2][0]["level"], int)


# ======================================================================
# WorkflowLogEmitter — batch flush
# ======================================================================

@pytest.mark.asyncio
async def test_workflow_log_emitter_flushes_on_batch_size() -> None:
    class DummyService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

        def is_enabled_for(self, _level: WorkflowLogLevelName) -> bool:
            return True

        async def upload_batch_async(self, records: list[WorkflowLogRequest]) -> None:
            self.batches.append(records)

    service = DummyService()
    emitter = WorkflowLogEmitter(
        log_service=service,  # type: ignore[arg-type]
        agent="Agent",
        workflow_type="Agent:Flow",
        workflow_id="tenant:Agent:Flow:activation-1",
        workflow_run_id="run-1",
        activation="activation-1",
        participant_id="user-1",
        tenant_id="tenant",
        batch_size=2,
        flush_interval_seconds=3600.0,
    )

    await emitter.emit_info("one")
    assert len(service.batches) == 0
    await emitter.emit_info("two")
    assert len(service.batches) == 1
    assert len(service.batches[0]) == 2
    assert service.batches[0][0].created_at is not None


@pytest.mark.asyncio
async def test_workflow_log_emitter_flushes_on_time_interval() -> None:
    class DummyService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

        def is_enabled_for(self, _level: WorkflowLogLevelName) -> bool:
            return True

        async def upload_batch_async(self, records: list[WorkflowLogRequest]) -> None:
            self.batches.append(records)

    service = DummyService()
    emitter = WorkflowLogEmitter(
        log_service=service,  # type: ignore[arg-type]
        agent="Agent",
        workflow_type="Agent:Flow",
        workflow_id="tenant:Agent:Flow:activation-1",
        workflow_run_id="run-1",
        activation="activation-1",
        participant_id="user-1",
        tenant_id="tenant",
        batch_size=100,
        flush_interval_seconds=0.0,
    )

    await emitter.emit_info("delayed")
    assert len(service.batches) == 1
    assert len(service.batches[0]) == 1


@pytest.mark.asyncio
async def test_workflow_log_emitter_emit_error_formats_exception() -> None:
    class DummyService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

        def is_enabled_for(self, _level: WorkflowLogLevelName) -> bool:
            return True

        async def upload_batch_async(self, records: list[WorkflowLogRequest]) -> None:
            self.batches.append(records)

    service = DummyService()
    emitter = WorkflowLogEmitter(
        log_service=service,  # type: ignore[arg-type]
        agent="Agent",
        workflow_type="Agent:Flow",
        workflow_id="tenant:Agent:Flow:activation-1",
        workflow_run_id="run-1",
        activation="activation-1",
        participant_id="user-1",
        tenant_id="tenant",
    )

    try:
        raise ValueError("boom")
    except ValueError as exc:
        await emitter.emit_error("failed", exc=exc)

    await emitter.flush()
    assert len(service.batches) == 1
    assert len(service.batches[0]) == 1
    assert service.batches[0][0].exception is not None
    assert "ValueError: boom" in service.batches[0][0].exception


# ======================================================================
# WorkflowLogService — level gating
# ======================================================================

def test_workflow_log_service_level_gate_default_disabled() -> None:
    class DummyClient:
        async def upload_agent_logs(self, payload: list[dict]) -> None:
            return

    service = WorkflowLogService(DummyClient())  # type: ignore[arg-type]
    assert service.is_enabled_for(WorkflowLogLevelName.Information) is False


def test_workflow_log_service_level_gate_enabled_at_information() -> None:
    class DummyClient:
        async def upload_agent_logs(self, payload: list[dict]) -> None:
            return

    service = WorkflowLogService(
        DummyClient(),  # type: ignore[arg-type]
        min_server_log_level="Information",
    )
    assert service.is_enabled_for(WorkflowLogLevelName.Debug) is False
    assert service.is_enabled_for(WorkflowLogLevelName.Information) is True
    assert service.is_enabled_for(WorkflowLogLevelName.Error) is True


# ======================================================================
# LoggerFactory — level parsing
# ======================================================================

def test_logger_factory_parse_log_level_valid() -> None:
    from xians.agents.workflow_logs.logger_factory import parse_log_level

    assert parse_log_level("DEBUG") == logging.DEBUG
    assert parse_log_level("debug") == logging.DEBUG
    assert parse_log_level("INFO") == logging.INFO
    assert parse_log_level("INFORMATION") == logging.INFO
    assert parse_log_level("WARNING") == logging.WARNING
    assert parse_log_level("WARN") == logging.WARNING
    assert parse_log_level("ERROR") == logging.ERROR
    assert parse_log_level("CRITICAL") == logging.CRITICAL


def test_logger_factory_parse_log_level_default() -> None:
    from xians.agents.workflow_logs.logger_factory import parse_log_level

    assert parse_log_level(None) == logging.INFO
    assert parse_log_level("") == logging.INFO
    assert parse_log_level("INVALID") == logging.INFO
    assert parse_log_level(None, default=logging.ERROR) == logging.ERROR


def test_logger_factory_get_console_log_level_env() -> None:
    from xians.agents.workflow_logs.logger_factory import get_console_log_level, reset

    reset()
    old = os.environ.get("CONSOLE_LOG_LEVEL")
    try:
        os.environ["CONSOLE_LOG_LEVEL"] = "ERROR"
        assert get_console_log_level() == logging.ERROR
    finally:
        if old is None:
            os.environ.pop("CONSOLE_LOG_LEVEL", None)
        else:
            os.environ["CONSOLE_LOG_LEVEL"] = old
        reset()


def test_logger_factory_get_server_log_level_env() -> None:
    from xians.agents.workflow_logs.logger_factory import get_server_log_level, reset

    reset()
    old_server = os.environ.get("SERVER_LOG_LEVEL")
    old_api = os.environ.get("API_LOG_LEVEL")
    try:
        os.environ.pop("SERVER_LOG_LEVEL", None)
        os.environ.pop("API_LOG_LEVEL", None)
        assert get_server_log_level() == logging.ERROR

        os.environ["SERVER_LOG_LEVEL"] = "DEBUG"
        assert get_server_log_level() == logging.DEBUG

        os.environ.pop("SERVER_LOG_LEVEL", None)
        os.environ["API_LOG_LEVEL"] = "WARNING"
        assert get_server_log_level() == logging.WARNING
    finally:
        if old_server is None:
            os.environ.pop("SERVER_LOG_LEVEL", None)
        else:
            os.environ["SERVER_LOG_LEVEL"] = old_server
        if old_api is None:
            os.environ.pop("API_LOG_LEVEL", None)
        else:
            os.environ["API_LOG_LEVEL"] = old_api
        reset()


def test_logger_factory_configure_log_levels_override() -> None:
    from xians.agents.workflow_logs.logger_factory import (
        configure_log_levels,
        get_console_log_level,
        get_server_log_level,
        reset,
    )

    try:
        configure_log_levels(
            console_log_level=logging.CRITICAL,
            server_log_level=logging.DEBUG,
        )
        assert get_console_log_level() == logging.CRITICAL
        assert get_server_log_level() == logging.DEBUG
    finally:
        reset()


def test_logger_factory_should_log_workflow_to_console() -> None:
    from xians.agents.workflow_logs.logger_factory import should_log_workflow_to_console

    old = os.environ.get("WORKFLOW_LOG_TO_CONSOLE")
    try:
        os.environ.pop("WORKFLOW_LOG_TO_CONSOLE", None)
        assert should_log_workflow_to_console() is True

        os.environ["WORKFLOW_LOG_TO_CONSOLE"] = "false"
        assert should_log_workflow_to_console() is False

        os.environ["WORKFLOW_LOG_TO_CONSOLE"] = "0"
        assert should_log_workflow_to_console() is False

        os.environ["WORKFLOW_LOG_TO_CONSOLE"] = "true"
        assert should_log_workflow_to_console() is True
    finally:
        if old is None:
            os.environ.pop("WORKFLOW_LOG_TO_CONSOLE", None)
        else:
            os.environ["WORKFLOW_LOG_TO_CONSOLE"] = old


# ======================================================================
# LoggingServices — enqueue + shutdown
# ======================================================================

def test_logging_services_enqueue_before_init_is_noop() -> None:
    LoggingServices.reset_for_tests()
    assert LoggingServices.is_initialized() is False

    req = WorkflowLogRequest(
        message="should be ignored",
        level=WorkflowLogLevelName.Error,
        workflow_id="t:A:W",
        agent="A",
    )
    LoggingServices.enqueue_log(req)
    assert LoggingServices._global_log_queue.empty()


@pytest.mark.asyncio
async def test_logging_services_initialize_and_enqueue() -> None:
    LoggingServices.reset_for_tests()

    class DummyLogService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

        def is_enabled_for(self, _level: WorkflowLogLevelName) -> bool:
            return True

        async def upload_batch_async(self, records: list[WorkflowLogRequest]) -> None:
            self.batches.append(records)

    dummy_service = DummyLogService()
    LoggingServices.initialize(dummy_service)  # type: ignore[arg-type]

    assert LoggingServices.is_initialized() is True

    req = WorkflowLogRequest(
        message="hello",
        level=WorkflowLogLevelName.Information,
        workflow_id="t:A:W",
        agent="A",
    )
    LoggingServices.enqueue_log(req)

    queued, _ = LoggingServices.get_logging_stats()
    assert queued >= 1

    LoggingServices.shutdown()
    assert LoggingServices.is_initialized() is False


def test_logging_services_configure_batch_settings() -> None:
    LoggingServices.reset_for_tests()
    LoggingServices.configure_batch_settings(batch_size=50, processing_interval_seconds=10)
    assert LoggingServices._batch_size == 50
    assert LoggingServices._processing_interval_seconds == 10

    with pytest.raises(ValueError):
        LoggingServices.configure_batch_settings(batch_size=0)
    with pytest.raises(ValueError):
        LoggingServices.configure_batch_settings(processing_interval_seconds=-1)

    LoggingServices.reset_for_tests()


# ======================================================================
# XiansLogger — caching and level dispatch
# ======================================================================

def test_xians_logger_for_type_caches_instance() -> None:
    from xians.agents.workflow_logs.xians_logger import XiansLogger

    XiansLogger.clear_cache()

    class MyClass:
        pass

    logger1 = XiansLogger.for_type(MyClass)
    logger2 = XiansLogger.for_type(MyClass)
    assert logger1 is logger2

    XiansLogger.clear_cache()


def test_xians_logger_for_name_caches_instance() -> None:
    from xians.agents.workflow_logs.xians_logger import XiansLogger

    XiansLogger.clear_cache()

    logger1 = XiansLogger.for_name("test.module")
    logger2 = XiansLogger.for_name("test.module")
    assert logger1 is logger2

    logger3 = XiansLogger.for_name("other.module")
    assert logger1 is not logger3

    XiansLogger.clear_cache()


def test_xians_logger_different_types_different_instances() -> None:
    from xians.agents.workflow_logs.xians_logger import XiansLogger

    XiansLogger.clear_cache()

    class A:
        pass

    class B:
        pass

    assert XiansLogger.for_type(A) is not XiansLogger.for_type(B)
    XiansLogger.clear_cache()


def test_xians_logger_log_methods_do_not_raise() -> None:
    from xians.agents.workflow_logs.xians_logger import XiansLogger

    XiansLogger.clear_cache()
    logger = XiansLogger.for_name("test.no_raise")
    logger.log_trace("trace")
    logger.log_debug("debug")
    logger.log_info("info")
    logger.log_information("information")
    logger.log_warning("warning")
    logger.log_error("error")
    logger.log_error("error with exc", exc=ValueError("boom"))
    logger.log_critical("critical")
    logger.log_critical("critical with exc", exc=RuntimeError("oops"))
    XiansLogger.clear_cache()


# ======================================================================
# ApiLoggerHandler — basic behaviour
# ======================================================================

def test_api_logger_handler_respects_server_level() -> None:
    from xians.agents.workflow_logs.api_logger_handler import ApiLoggerHandler
    from xians.agents.workflow_logs.logger_factory import configure_log_levels, reset

    try:
        configure_log_levels(server_log_level=logging.ERROR)
        handler = ApiLoggerHandler()

        record_info = logging.LogRecord(
            "test", logging.INFO, "", 0, "info msg", (), None
        )
        record_error = logging.LogRecord(
            "test", logging.ERROR, "", 0, "error msg", (), None
        )

        LoggingServices.reset_for_tests()

        handler.emit(record_info)
        assert LoggingServices._global_log_queue.empty()

        handler.emit(record_error)
        # Not initialized, so still empty (enqueue is noop before init)
        assert LoggingServices._global_log_queue.empty()
    finally:
        reset()
        LoggingServices.reset_for_tests()


def test_api_logger_handler_temporal_message_processing() -> None:
    from xians.agents.workflow_logs.api_logger_handler import _process_temporal_message

    assert _process_temporal_message("ActivityFailureException occurred", logging.ERROR) == logging.CRITICAL
    assert _process_temporal_message("Activity task failed for X", logging.DEBUG - 5) == logging.CRITICAL
    assert _process_temporal_message("Regular info log", logging.INFO) == logging.INFO
    assert _process_temporal_message('Sending activity completion "failed"', logging.DEBUG - 5) == logging.ERROR


# ======================================================================
# WorkflowLogEmitter — new level methods (emit_trace, emit_warning, emit_critical)
# ======================================================================

@pytest.mark.asyncio
async def test_workflow_log_emitter_new_level_methods() -> None:
    class DummyService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

        def is_enabled_for(self, _level: WorkflowLogLevelName) -> bool:
            return True

        async def upload_batch_async(self, records: list[WorkflowLogRequest]) -> None:
            self.batches.append(records)

    service = DummyService()
    emitter = WorkflowLogEmitter(
        log_service=service,  # type: ignore[arg-type]
        agent="Agent",
        workflow_type="Agent:Flow",
        workflow_id="t:A:F:p",
        workflow_run_id="run",
        activation="p",
        participant_id="u",
        tenant_id="t",
    )

    await emitter.emit_trace("trace msg")
    await emitter.emit_debug("debug msg")
    await emitter.emit_info("info msg")
    await emitter.emit_warning("warning msg")
    await emitter.emit_error("error msg")
    await emitter.emit_critical("critical msg")
    await emitter.flush()

    assert len(service.batches) == 1
    levels = [r.level for r in service.batches[0]]
    assert levels == [
        WorkflowLogLevelName.Trace,
        WorkflowLogLevelName.Debug,
        WorkflowLogLevelName.Information,
        WorkflowLogLevelName.Warning,
        WorkflowLogLevelName.Error,
        WorkflowLogLevelName.Critical,
    ]


# ======================================================================
# Constants — sanity checks
# ======================================================================

def test_constants_exist() -> None:
    from xians.agents.workflow_logs.constants import (
        CONSOLE_LOG_LEVEL_ENV,
        SERVER_LOG_LEVEL_ENV,
        API_LOG_LEVEL_ENV,
        WORKFLOW_LOG_TO_CONSOLE_ENV,
        LOGS_API_ENDPOINT,
        DEFAULT_BATCH_SIZE,
        DEFAULT_PROCESSING_INTERVAL_SECONDS,
        MAX_RETRIES,
    )

    assert CONSOLE_LOG_LEVEL_ENV == "CONSOLE_LOG_LEVEL"
    assert SERVER_LOG_LEVEL_ENV == "SERVER_LOG_LEVEL"
    assert API_LOG_LEVEL_ENV == "API_LOG_LEVEL"
    assert WORKFLOW_LOG_TO_CONSOLE_ENV == "WORKFLOW_LOG_TO_CONSOLE"
    assert LOGS_API_ENDPOINT == "api/agent/logs"
    assert DEFAULT_BATCH_SIZE == 100
    assert DEFAULT_PROCESSING_INTERVAL_SECONDS == 30
    assert MAX_RETRIES == 3
