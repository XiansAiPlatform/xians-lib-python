"""Metrics models matching C# Xians.Lib.Agents.Metrics.Models.

Used for flexible usage reporting via POST /api/agent/usage/report.
"""

from typing import Any

from pydantic import BaseModel, Field


class MetricValue(BaseModel):
    """Represents a single metric value with category, type, and unit.

    Matches C# MetricValue.
    """

    category: str = Field(description="Metric category (e.g., 'tokens', 'workflow_approval')")
    type: str = Field(description="Metric type (e.g., 'total', 'submitted', 'prompt')")
    value: float = Field(description="Numeric value of the metric")
    unit: str = Field(default="count", description="Unit of measurement (e.g., 'count', 'tokens', 'ms')")

    model_config = {"populate_by_name": True}


class UsageReportRequest(BaseModel):
    """Request model for flexible metrics reporting.

    Matches C# UsageReportRequest. Supports standard and custom metrics
    in a scalable array format.
    """

    tenant_id: str | None = Field(default=None, serialization_alias="tenantId")
    participant_id: str | None = Field(default=None, serialization_alias="participantId")
    workflow_id: str | None = Field(default=None, serialization_alias="workflowId")
    request_id: str | None = Field(default=None, serialization_alias="requestId")
    workflow_type: str | None = Field(default=None, serialization_alias="workflowType")
    model: str | None = Field(default=None, serialization_alias="model")
    custom_identifier: str | None = Field(default=None, serialization_alias="customIdentifier")
    agent_name: str | None = Field(default=None, serialization_alias="agentName")
    activation_name: str | None = Field(default=None, serialization_alias="activationName")
    metrics: list[MetricValue] = Field(default_factory=list, serialization_alias="metrics")
    metadata: dict[str, str] | None = Field(default=None, serialization_alias="metadata")

    model_config = {"populate_by_name": True}

    def model_dump_for_api(self) -> dict[str, Any]:
        """Serialize for API with camelCase keys and exclude None."""
        return self.model_dump(by_alias=True, exclude_none=True)


__all__ = ["MetricValue", "UsageReportRequest"]
