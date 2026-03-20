"""Core service for metrics reporting via HTTP client.

Matches C# MetricsService. Handles direct HTTP operations for reporting
usage metrics to the Xians platform server.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import UsageReportRequest

if TYPE_CHECKING:
    from ...interfaces.v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class MetricsService:
    """Core service for metrics reporting via HTTP client.

    Shared by UsageActivities (workflow context) and direct calls (activity context).
    Matches C# MetricsService.
    """

    def __init__(
        self,
        http_client: XiansServerClient,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        self._http_client = http_client
        self._logger = logger_instance or logger

    async def report_async(
        self,
        request: UsageReportRequest,
    ) -> None:
        """Report flexible usage metrics to the Xians platform server.

        Safe to call even if the HTTP service has issues - logs warning and returns.
        Matches C# MetricsService.ReportAsync.
        """
        try:
            payload = request.model_dump_for_api()
            self._logger.info(
                "Reporting usage metrics: model=%s, metrics_count=%s, agent=%s, tenant=%s",
                request.model,
                len(request.metrics),
                request.agent_name,
                request.tenant_id,
            )
            await self._http_client.report_metrics_usage(payload)
            self._logger.info(
                "Usage reported successfully: model=%s, metrics_count=%s",
                request.model,
                len(request.metrics),
            )
        except Exception as ex:
            self._logger.warning("Failed to report usage metrics: %s", ex, exc_info=True)


__all__ = ["MetricsService"]
