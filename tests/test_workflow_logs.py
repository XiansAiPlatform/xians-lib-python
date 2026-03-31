"""Unit tests for workflow log ingestion payloads."""

import pytest

from xians.agents.workflow_logs.log_emitter import WorkflowLogEmitter
from xians.agents.workflow_logs.log_service import WorkflowLogService
from xians.agents.workflow_logs.models import (
    LOG_LEVEL_NAME_TO_NUMBER,
    WorkflowLogLevelName,
    WorkflowLogRequest,
)
from xians.exceptions.v1.errors import XiansServerError


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


@pytest.mark.asyncio
async def test_workflow_log_service_falls_back_on_level_format() -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        async def upload_agent_logs(self, payload: list[dict]) -> None:
            self.calls.append(payload)
            if payload and isinstance(payload[0].get("level"), str):
                # Simulate backend deserialization rejecting enum-name levels.
                raise XiansServerError("bad level format", status_code=400)
            return

    dummy = DummyClient()
    service = WorkflowLogService(dummy)  # type: ignore[arg-type]

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
    service = WorkflowLogService(dummy)  # type: ignore[arg-type]

    req = WorkflowLogRequest(
        message="x",
        level=WorkflowLogLevelName.Warning,
        workflow_id="tenant:Agent:Flow:activation-1",
        agent="Agent",
    )

    await service.upload_batch_async([req])
    await service.upload_batch_async([req])

    # First call name->number fallback (2 uploads), second call numeric only.
    assert len(dummy.calls) == 3
    assert isinstance(dummy.calls[0][0]["level"], str)
    assert isinstance(dummy.calls[1][0]["level"], int)
    assert isinstance(dummy.calls[2][0]["level"], int)


@pytest.mark.asyncio
async def test_workflow_log_emitter_flushes_on_batch_size() -> None:
    class DummyService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

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


@pytest.mark.asyncio
async def test_workflow_log_emitter_flushes_on_time_interval() -> None:
    class DummyService:
        def __init__(self) -> None:
            self.batches: list[list[WorkflowLogRequest]] = []

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

