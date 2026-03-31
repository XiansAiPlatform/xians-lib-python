"""Models for workflow log ingestion.

These models implement the backend ingestion contract for:
`POST /api/agent/logs`

Python is responsible for providing:
- correlation fields (agent/workflowType/workflowId/workflowRunId/activation/participantId)
- message + exception
- log level (serialized in a compatible format)
"""

from __future__ import annotations

import enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowLogLevelName(str, enum.Enum):
    Trace = "Trace"
    Debug = "Debug"
    Information = "Information"
    Warning = "Warning"
    Error = "Error"
    Critical = "Critical"


LOG_LEVEL_NAME_TO_NUMBER: dict[str, int] = {
    "Trace": 0,
    "Debug": 1,
    "Information": 2,
    "Warning": 3,
    "Error": 4,
    "Critical": 5,
}


class WorkflowLogRequest(BaseModel):
    """Single log record request for ingestion."""

    message: str = Field(min_length=1, description="Log message")
    level: WorkflowLogLevelName = Field(description="Backend log level (enum name)")

    # Required correlation fields for ingestion
    workflow_id: str = Field(
        min_length=1,
        serialization_alias="workflowId",
        description="Temporal workflow id used for correlation",
    )
    agent: str = Field(
        min_length=1,
        serialization_alias="agent",
        description="Agent name used for UI filtering",
    )

    # Strongly recommended correlation fields
    workflow_type: str | None = Field(default=None, serialization_alias="workflowType")
    workflow_run_id: str | None = Field(default=None, serialization_alias="workflowRunId")
    activation: str | None = Field(default=None, description="Activation / idPostfix")
    participant_id: str | None = Field(default=None, serialization_alias="participantId")
    tenant_id: str | None = Field(default=None, serialization_alias="tenantId")
    trace_id: str | None = Field(default=None, serialization_alias="traceId")
    span_id: str | None = Field(default=None, serialization_alias="spanId")

    # Error details
    exception: str | None = Field(default=None, description="Stringified stack trace or exception")

    # Server may assign createdAt; include only if needed.
    created_at: str | None = Field(default=None, serialization_alias="createdAt")

    model_config = {"populate_by_name": True}

    def to_api_dict(self, *, level_format: Literal["name", "number"] = "name") -> dict[str, Any]:
        """Serialize for ingestion payload.

        Args:
            level_format: "name" -> "Information", "Error"...; "number" -> 0..5 semantics.
        """
        data = self.model_dump(by_alias=True, exclude_none=True)

        if level_format == "name":
            # Ensure `level` is serialized as enum name string.
            data["level"] = self.level.value
        elif level_format == "number":
            data["level"] = LOG_LEVEL_NAME_TO_NUMBER[self.level.value]
        else:
            raise ValueError("level_format must be 'name' or 'number'")

        return data


__all__ = [
    "WorkflowLogLevelName",
    "WorkflowLogRequest",
    "LOG_LEVEL_NAME_TO_NUMBER",
]

