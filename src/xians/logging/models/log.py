"""Log entry model for server upload. Matches C# Xians.Lib.Logging.Models.Log."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Log(BaseModel):
    """Represents a log entry sent to the Xians server.

    Field names use camelCase aliases to match the server API contract.
    """

    id: Optional[str] = Field(default=None, alias="id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
    )
    level: str = Field(alias="level")
    message: str = Field(alias="message")
    workflow_id: Optional[str] = Field(default=None, alias="workflowId")
    workflow_run_id: Optional[str] = Field(default=None, alias="workflowRunId")
    workflow_type: Optional[str] = Field(default=None, alias="workflowType")
    agent: str = Field(default="", alias="agent")
    tenant_id: Optional[str] = Field(default=None, alias="tenantId")
    participant_id: Optional[str] = Field(default=None, alias="participantId")
    activation: Optional[str] = Field(default=None, alias="activation")
    exception: Optional[str] = Field(default=None, alias="exception")
    trace_id: Optional[str] = Field(default=None, alias="traceId")
    span_id: Optional[str] = Field(default=None, alias="spanId")

    model_config = {"populate_by_name": True}
