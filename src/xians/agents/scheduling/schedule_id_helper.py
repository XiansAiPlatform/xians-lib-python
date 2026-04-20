"""Helpers for building schedule and workflow IDs.

Mirrors C# ``Xians.Lib.Agents.Scheduling.ScheduleIdHelper``.
"""

from __future__ import annotations

from typing import Optional


class ScheduleIdHelper:
    """Utility methods for building fully-qualified schedule / workflow IDs."""

    @staticmethod
    def build_full_schedule_id(
        tenant_id: str,
        agent_name: str,
        id_postfix: Optional[str],
        schedule_name: str,
    ) -> str:
        """Build the full schedule ID using the pattern
        ``{tenantId}:{agentName}[:{idPostfix}]:{scheduleName}``.

        If ``id_postfix`` is ``None`` the postfix segment is omitted entirely
        (same semantics as the C# implementation).  An empty string for
        ``id_postfix`` is preserved as an explicit empty segment.
        """
        if id_postfix is None:
            return f"{tenant_id}:{agent_name}:{schedule_name}"
        return f"{tenant_id}:{agent_name}:{id_postfix}:{schedule_name}"

    @staticmethod
    def build_full_workflow_id(
        tenant_id: str,
        workflow_type: str,
        id_postfix: str,
    ) -> str:
        """Build the workflow ID prefix used for schedule-triggered workflows.

        Pattern: ``{tenantId}:{workflowType}:{idPostfix}``.
        """
        return f"{tenant_id}:{workflow_type}:{id_postfix}"


__all__ = ["ScheduleIdHelper"]
