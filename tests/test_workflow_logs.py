"""Unit tests for workflow log ingestion payloads."""

import pytest

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

