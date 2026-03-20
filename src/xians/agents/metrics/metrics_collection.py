"""Collection wrapper for metrics operations.

Matches C# MetricsCollection. Provides instance-level access to metrics
functionality with context-aware execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .context_aware_usage_report_builder import ContextAwareUsageReportBuilder
from .metrics_executor import MetricsExecutor
from .models import UsageReportRequest

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MetricsCollection:
    """Collection wrapper for metrics operations.

    Provides instance-level access to metrics functionality.
    Uses executor pattern for context-aware operations (workflow vs activity).
    Matches C# MetricsCollection.
    """

    def __init__(
        self,
        agent_name: str,
        http_client: object,
        platform: object | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._http_client = http_client
        self._platform = platform

    @property
    def agent_name(self) -> str:
        return self._agent_name

    async def report_async(self, request: UsageReportRequest) -> None:
        """Report usage metrics with automatic context detection.

        - In workflows: Uses UsageActivities (deterministic, no direct HTTP)
        - Outside workflows: Directly calls MetricsService (HTTP)
        """
        executor = MetricsExecutor(
            agent_name=self._agent_name,
            http_client=self._http_client,
            logger_instance=logger,
        )
        await executor.report_async(request)

    def track(self, context: object | None = None) -> ContextAwareUsageReportBuilder:
        """Start a fluent builder for tracking metrics with automatic context population.

        Auto-populates tenant ID, workflow ID, user ID, etc. from XiansContext when available.
        """
        return ContextAwareUsageReportBuilder(self, context)

    # ------------------------------------------------------------------
    # Fluent builder shortcuts - direct access without track()
    # ------------------------------------------------------------------

    def for_model(self, model: str) -> ContextAwareUsageReportBuilder:
        """Set the model name. Creates a new builder populated from XiansContext."""
        return self.track().for_model(model)

    def with_metric(
        self,
        category: str,
        type: str,
        value: float,
        unit: str = "count",
    ) -> ContextAwareUsageReportBuilder:
        """Add a single metric. Creates a new builder populated from XiansContext."""
        return self.track().with_metric(category, type, value, unit)

    def with_metrics(
        self,
        *metrics: tuple[str, str, float, str],
    ) -> ContextAwareUsageReportBuilder:
        """Add multiple metrics. Creates a new builder populated from XiansContext."""
        return self.track().with_metrics(*metrics)

    def with_tenant_id(self, tenant_id: str) -> ContextAwareUsageReportBuilder:
        """Set the tenant ID."""
        return self.track().with_tenant_id(tenant_id)

    def with_user_id(self, user_id: str) -> ContextAwareUsageReportBuilder:
        """Set the user/participant ID."""
        return self.track().with_user_id(user_id)

    def with_workflow_id(self, workflow_id: str) -> ContextAwareUsageReportBuilder:
        """Set the workflow ID."""
        return self.track().with_workflow_id(workflow_id)

    def with_request_id(self, request_id: str) -> ContextAwareUsageReportBuilder:
        """Set the request ID."""
        return self.track().with_request_id(request_id)

    def from_source(self, source: str) -> ContextAwareUsageReportBuilder:
        """Set the source identifier."""
        return self.track().from_source(source)

    def with_custom_identifier(self, custom_identifier: str) -> ContextAwareUsageReportBuilder:
        """Set a custom identifier."""
        return self.track().with_custom_identifier(custom_identifier)

    def with_metadata(self, key: str, value: str) -> ContextAwareUsageReportBuilder:
        """Add a metadata key-value pair."""
        return self.track().with_metadata(key, value)

    def with_metadata_dict(self, metadata: dict[str, str]) -> ContextAwareUsageReportBuilder:
        """Add multiple metadata entries."""
        return self.track().with_metadata_dict(metadata)


__all__ = ["MetricsCollection"]
