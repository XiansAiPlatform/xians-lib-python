"""HTTP uploader for workflow logs.

Implements:
  POST /api/agent/logs
with request body as a JSON array.

Level serialization can differ between backend implementations:
- enum names: "Information", "Error"...
- numeric ordinals: 0..5

To be robust, we try enum-name serialization first and fall back to numeric
serialization on HTTP 400.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...exceptions.v1.errors import XiansServerError
from .models import WorkflowLogRequest

if TYPE_CHECKING:
    from ...interfaces.v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class WorkflowLogService:
    def __init__(self, xians_client: "XiansServerClient", logger_instance: logging.Logger | None = None) -> None:
        self._client = xians_client
        self._logger = logger_instance or logger
        self._prefer_numeric_levels = False

    async def upload_batch_async(self, records: list[WorkflowLogRequest]) -> None:
        """Upload a batch of log records (best-effort)."""
        if not records:
            return

        if self._prefer_numeric_levels:
            payload_number = [r.to_api_dict(level_format="number") for r in records]
            try:
                await self._client.upload_agent_logs(payload_number)
                return
            except Exception as ex:
                self._logger.warning("Failed to upload workflow logs: %s", ex, exc_info=True)
                return

        payload_name = [r.to_api_dict(level_format="name") for r in records]
        try:
            await self._client.upload_agent_logs(payload_name)
            return
        except XiansServerError as ex:
            # Common issue: backend expects numeric ordinals (not enum names).
            if ex.status_code == 400:
                payload_number = [r.to_api_dict(level_format="number") for r in records]
                try:
                    await self._client.upload_agent_logs(payload_number)
                    self._prefer_numeric_levels = True
                    self._logger.info(
                        "Uploaded workflow logs using numeric level fallback (%s records)",
                        len(records),
                    )
                    return
                except Exception as fallback_ex:
                    self._logger.warning(
                        "Failed to upload workflow logs (level fallback too): %s",
                        fallback_ex,
                        exc_info=True,
                    )
                    return

            self._logger.warning(
                "Failed to upload workflow logs: %s",
                ex,
                exc_info=True,
            )
            return
        except Exception as ex:
            self._logger.warning("Failed to upload workflow logs: %s", ex, exc_info=True)
            return


__all__ = ["WorkflowLogService"]

