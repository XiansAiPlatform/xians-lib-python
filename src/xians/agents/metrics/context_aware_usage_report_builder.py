"""Context-aware fluent builder for constructing and reporting usage metrics.

Matches C# ContextAwareUsageReportBuilder. Automatically populates context
information from XiansContext when available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...agents.core.xians_context import XiansContext
from .models import MetricValue, UsageReportRequest

if TYPE_CHECKING:
    from .metrics_collection import MetricsCollection


class ContextAwareUsageReportBuilder:
    """Context-aware fluent builder for constructing and reporting usage metrics.

    Automatically populates context information from XiansContext when available.
    Matches C# ContextAwareUsageReportBuilder.
    """

    def __init__(
        self,
        metrics_collection: MetricsCollection,
        context: object | None = None,
    ) -> None:
        self._metrics_collection = metrics_collection
        self._context = context
        self._metrics: list[MetricValue] = []
        self._tenant_id: str | None = None
        self._user_id: str | None = None
        self._workflow_id: str | None = None
        self._request_id: str | None = None
        self._model: str | None = None
        self._source: str | None = None
        self._custom_identifier: str | None = None
        self._metadata: dict[str, str] | None = None

    def with_tenant_id(self, tenant_id: str) -> "ContextAwareUsageReportBuilder":
        """Set the tenant ID (defaults to XiansContext when available)."""
        self._tenant_id = tenant_id
        return self

    def with_user_id(self, user_id: str) -> "ContextAwareUsageReportBuilder":
        """Set the user/participant ID (defaults to current workflow's participant if available)."""
        self._user_id = user_id
        return self

    def with_workflow_id(self, workflow_id: str) -> "ContextAwareUsageReportBuilder":
        """Set the workflow ID (defaults to XiansContext when available)."""
        self._workflow_id = workflow_id
        return self

    def with_request_id(self, request_id: str) -> "ContextAwareUsageReportBuilder":
        """Set the request ID."""
        self._request_id = request_id
        return self

    def for_model(self, model: str) -> "ContextAwareUsageReportBuilder":
        """Set the model name (e.g., 'gpt-4', 'claude-3-opus')."""
        self._model = model
        return self

    def from_source(self, source: str) -> "ContextAwareUsageReportBuilder":
        """Set the source identifier (defaults to current workflow type if available)."""
        self._source = source
        return self

    def with_custom_identifier(self, custom_identifier: str) -> "ContextAwareUsageReportBuilder":
        """Set a custom identifier to link this usage event to client/agent-specific data."""
        self._custom_identifier = custom_identifier
        return self

    def with_metric(
        self,
        category: str,
        type: str,
        value: float,
        unit: str = "count",
    ) -> "ContextAwareUsageReportBuilder":
        """Add a single metric."""
        self._metrics.append(
            MetricValue(category=category, type=type, value=value, unit=unit)
        )
        return self

    def with_metrics(
        self,
        *metrics: tuple[str, str, float, str],
    ) -> "ContextAwareUsageReportBuilder":
        """Add multiple metrics at once using tuple syntax.
        Each tuple: (category, type, value, unit).
        """
        for category, type_val, value, unit in metrics:
            self._metrics.append(
                MetricValue(category=category, type=type_val, value=value, unit=unit)
            )
        return self

    def with_metadata(self, key: str, value: str) -> "ContextAwareUsageReportBuilder":
        """Add a metadata key-value pair."""
        if self._metadata is None:
            self._metadata = {}
        self._metadata[key] = value
        return self

    def with_metadata_dict(self, metadata: dict[str, str]) -> "ContextAwareUsageReportBuilder":
        """Add multiple metadata entries."""
        self._metadata = metadata
        return self

    def _resolve_tenant_id(self) -> str | None:
        if self._tenant_id:
            return self._tenant_id
        if self._context and hasattr(self._context, "message"):
            msg = getattr(self._context, "message", None)
            if msg and hasattr(msg, "tenant_id"):
                return getattr(msg, "tenant_id") or None
        return XiansContext.safe_tenant_id()

    def _resolve_participant_id(self) -> str | None:
        if self._user_id:
            return self._user_id
        if self._context and hasattr(self._context, "message"):
            msg = getattr(self._context, "message", None)
            if msg and hasattr(msg, "participant_id"):
                return getattr(msg, "participant_id") or None
        return XiansContext.safe_participant_id()

    def _resolve_workflow_id(self) -> str | None:
        if self._workflow_id:
            return self._workflow_id
        # A2A: for target workflow context, use target_workflow_id if available
        if self._context and hasattr(self._context, "target_workflow_id"):
            tid = getattr(self._context, "target_workflow_id", None)
            if tid:
                return tid
        return XiansContext.safe_workflow_id()

    def _resolve_request_id(self) -> str | None:
        if self._request_id:
            return self._request_id
        if self._context and hasattr(self._context, "message"):
            msg = getattr(self._context, "message", None)
            if msg and hasattr(msg, "request_id"):
                return getattr(msg, "request_id") or None
        return XiansContext.get_request_id()

    def _resolve_workflow_type(self) -> str:
        if self._source:
            return self._source
        # A2A: use target workflow type if available
        if self._context and hasattr(self._context, "target_workflow_type"):
            ttype = getattr(self._context, "target_workflow_type", None)
            if ttype:
                return ttype
        return XiansContext.safe_workflow_type() or "Unknown"

    async def report_async(self) -> None:
        """Report the usage metrics with automatic context detection.

        Automatically populates tenantId, agentName, activationName, participantId,
        workflowId, and requestId from XiansContext without requiring explicit calls.
        """
        tenant_id = self._resolve_tenant_id()
        participant_id = self._resolve_participant_id()
        workflow_id = self._resolve_workflow_id()
        request_id = self._resolve_request_id()
        workflow_type = self._resolve_workflow_type()
        agent_name = XiansContext.safe_agent_name() or self._metrics_collection.agent_name
        activation_name = XiansContext.safe_id_postfix()

        request = UsageReportRequest(
            tenant_id=tenant_id,
            participant_id=participant_id,
            workflow_id=workflow_id,
            request_id=request_id,
            workflow_type=workflow_type,
            model=self._model,
            custom_identifier=self._custom_identifier,
            agent_name=agent_name,
            activation_name=activation_name,
            metrics=self._metrics,
            metadata=self._metadata,
        )

        await self._metrics_collection.report_async(request)


__all__ = ["ContextAwareUsageReportBuilder"]
