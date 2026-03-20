"""Temporal activities for reporting usage metrics from workflows.

Matches C# UsageActivities. Automatically registered with all workflows.
Activities can perform non-deterministic operations like HTTP calls.
"""

from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from .metrics_service import MetricsService
from .models import MetricValue, UsageReportRequest

logger = logging.getLogger(__name__)


class UsageActivities:
    """System activity for reporting usage metrics from workflows.

    Matches C# UsageActivities. Wraps MetricsService to allow workflows
    to track usage via Temporal activities (deterministic from workflow perspective).
    """

    def __init__(self, http_client: object) -> None:
        self._http_client = http_client
        self._logger = logging.getLogger(f"{__name__}.UsageActivities")

    @activity.defn(name="ReportUsage")
    async def report_usage(self, request_payload: dict[str, Any]) -> None:
        """Report usage metrics to the Xians platform.

        Receives serialized UsageReportRequest (dict) from workflow.
        Matches C# UsageActivities.ReportUsageAsync.
        """
        activity.logger.debug(
            "ReportUsage activity started: tenant_id=%s, workflow_type=%s, metrics_count=%s",
            request_payload.get("tenantId"),
            request_payload.get("workflowType"),
            len(request_payload.get("metrics", [])),
        )

        try:
            # Reconstruct UsageReportRequest from payload
            metrics = [
                MetricValue(
                    category=m["category"],
                    type=m["type"],
                    value=float(m["value"]),
                    unit=m.get("unit", "count"),
                )
                for m in request_payload.get("metrics", [])
            ]

            request = UsageReportRequest(
                tenant_id=request_payload.get("tenantId"),
                participant_id=request_payload.get("participantId"),
                workflow_id=request_payload.get("workflowId"),
                request_id=request_payload.get("requestId"),
                workflow_type=request_payload.get("workflowType"),
                model=request_payload.get("model"),
                custom_identifier=request_payload.get("customIdentifier"),
                agent_name=request_payload.get("agentName"),
                activation_name=request_payload.get("activationName"),
                metrics=metrics,
                metadata=request_payload.get("metadata"),
            )

            service = MetricsService(self._http_client, self._logger)
            await service.report_async(request)

            activity.logger.debug(
                "Usage metrics reported successfully: tenant_id=%s, workflow_type=%s",
                request.tenant_id,
                request.workflow_type,
            )
        except Exception as ex:
            activity.logger.error(
                "Error reporting usage metrics: %s",
                ex,
                exc_info=True,
            )
            raise


__all__ = ["UsageActivities"]
