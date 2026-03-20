"""Activity executor for metrics operations.

Matches C# MetricsActivityExecutor. Handles context-aware execution:
- In workflows: Uses UsageActivities (deterministic, no direct HTTP)
- Outside workflows: Directly calls MetricsService (HTTP)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...agents.core.xians_context import XiansContext
from .metrics_service import MetricsService
from .models import UsageReportRequest

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MetricsExecutor:
    """Activity executor for metrics operations.

    Handles context-aware execution of metrics activities.
    Matches C# MetricsActivityExecutor / ContextAwareActivityExecutor pattern.
    """

    def __init__(
        self,
        agent_name: str,
        http_client: object,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._http_client = http_client
        self._logger = logger_instance or logger

    async def report_async(self, request: UsageReportRequest) -> None:
        """Report usage metrics with automatic context detection.

        - In workflows: Uses UsageActivities (deterministic, no direct HTTP)
        - Outside workflows: Directly calls MetricsService (HTTP)
        """
        if XiansContext.in_workflow():
            self._logger.debug(
                "Executing ReportUsage via activity in workflow context"
            )
            from datetime import timedelta

            from temporalio import workflow

            # Execute by activity name - UsageActivities must be registered with worker
            await workflow.execute_activity(
                "ReportUsage",
                request.model_dump_for_api(),
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            self._logger.debug(
                "Executing ReportUsage via direct service call in activity context"
            )
            service = MetricsService(self._http_client, self._logger)
            await service.report_async(request)


__all__ = ["MetricsExecutor"]
