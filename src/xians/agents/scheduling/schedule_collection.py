"""Agent-level collection of schedules.

Mirrors C# ``Xians.Lib.Agents.Scheduling.ScheduleCollection``. One instance is
created per :class:`AgentRegistration` and exposes ``create``/``get``/``exists``/
``pause``/``unpause``/``trigger``/``delete`` operations.

The collection takes a callable that asynchronously returns a connected
:class:`temporalio.client.Client`.  This indirection keeps the collection
usable even when the platform's Temporal connection is established lazily
(after ``XiansPlatform.run_all``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from ..core.xians_context import XiansContext
from .models.exceptions import ScheduleNotFoundError
from .schedule_builder import ScheduleBuilder
from .schedule_id_helper import ScheduleIdHelper
from .xians_schedule import XiansSchedule

# Ensure the fluent extension methods (daily, every_minutes, skip_if_running,
# …) are attached to ScheduleBuilder as soon as the collection is imported.
from . import schedule_extensions as _schedule_extensions  # noqa: F401

if TYPE_CHECKING:
    from temporalio.client import Client


logger = logging.getLogger(__name__)


TemporalClientProvider = Callable[[], Awaitable[Optional["Client"]]]


class ScheduleCollection:
    """Manages schedules for a specific agent.

    Instantiated internally by :class:`AgentRegistration`. Callers typically
    interact with this collection via ``XiansContext.CurrentAgent.schedules``
    or ``agent.schedules`` from the platform registration.
    """

    def __init__(
        self,
        *,
        agent_name: str,
        system_scoped: bool,
        tenant_id: Optional[str],
        get_temporal_client: TemporalClientProvider,
    ) -> None:
        if not agent_name:
            raise ValueError("agent_name cannot be empty")
        self._agent_name = agent_name
        self._system_scoped = system_scoped
        self._tenant_id = tenant_id
        self._get_temporal_client = get_temporal_client

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create(
        self,
        schedule_name: str,
        workflow_type_or_class: object,
        id_postfix: Optional[str] = None,
    ) -> ScheduleBuilder:
        """Start building a schedule for ``workflow_type_or_class``.

        Args:
            schedule_name: Unique (per tenant/agent/idPostfix) schedule name.
            workflow_type_or_class: Either the Temporal workflow type string
                (e.g. ``"MyAgent:DailyReport"``) or a class decorated with
                ``@workflow.defn(name=...)``.
            id_postfix: Optional postfix appended to the schedule and workflow
                IDs (ensures per-run/per-user uniqueness).  When omitted the
                current workflow context's ``idPostfix`` is used if available.

        Returns:
            A :class:`ScheduleBuilder` for further fluent configuration.
        """
        workflow_type = self._resolve_workflow_type(workflow_type_or_class)
        if not schedule_name or not workflow_type:
            raise ValueError(
                "schedule_name and workflow_type are required and cannot be empty"
            )
        return ScheduleBuilder(
            schedule_name=schedule_name,
            agent_name=self._agent_name,
            system_scoped=self._system_scoped,
            tenant_id=self._tenant_id,
            workflow_type=workflow_type,
            collection=self,
            id_postfix=id_postfix,
        )

    @staticmethod
    def _resolve_workflow_type(workflow_type_or_class: object) -> str:
        """Accept a workflow class decorated with ``@workflow.defn`` or a string."""
        if isinstance(workflow_type_or_class, str):
            return workflow_type_or_class
        defn = getattr(workflow_type_or_class, "__temporal_workflow_definition", None)
        if defn is not None and getattr(defn, "name", None):
            return defn.name
        raise ValueError(
            "workflow_type_or_class must be a workflow type string or a class "
            "decorated with @workflow.defn(name='...')"
        )

    # ------------------------------------------------------------------
    # Lookup / existence
    # ------------------------------------------------------------------

    async def get_async(
        self, schedule_name: str, id_postfix: Optional[str] = None
    ) -> XiansSchedule:
        """Retrieve an existing schedule.

        Raises:
            ScheduleNotFoundError: when the schedule cannot be found.
        """
        if not schedule_name:
            raise ValueError("schedule_name cannot be empty")

        effective_postfix = (
            id_postfix if id_postfix is not None else XiansContext.safe_id_postfix()
        )
        tenant_id = self._effective_tenant_id()
        full_schedule_id = ScheduleIdHelper.build_full_schedule_id(
            tenant_id, self._agent_name, effective_postfix, schedule_name
        )

        client = await self._require_client()
        try:
            handle = client.get_schedule_handle(full_schedule_id)
            await handle.describe()
        except Exception as ex:
            message = str(ex).lower()
            if "not found" in message or "does not exist" in message:
                # Logged at debug level: callers like exists_async routinely
                # hit this path and the warning was noisy for no reason.
                logger.debug("Schedule '%s' not found", schedule_name)
                raise ScheduleNotFoundError(schedule_name, cause=ex) from ex
            logger.error("Failed to get schedule '%s': %s", schedule_name, ex)
            raise
        return XiansSchedule(handle)

    async def exists_async(
        self, schedule_name: str, id_postfix: Optional[str] = None
    ) -> bool:
        """Check whether a schedule with the given name exists.

        Resolves via a direct Temporal ``describe`` call so probing the
        Temporal server for the schedule's presence never produces a
        user-facing warning — the absence of a schedule is normal here.
        """
        if not schedule_name:
            raise ValueError("schedule_name cannot be empty")

        effective_postfix = (
            id_postfix if id_postfix is not None else XiansContext.safe_id_postfix()
        )
        tenant_id = self._effective_tenant_id()
        full_schedule_id = ScheduleIdHelper.build_full_schedule_id(
            tenant_id, self._agent_name, effective_postfix, schedule_name
        )

        client = await self._require_client()
        try:
            handle = client.get_schedule_handle(full_schedule_id)
            await handle.describe()
        except Exception as ex:
            message = str(ex).lower()
            if "not found" in message or "does not exist" in message:
                return False
            logger.error("Failed to check schedule '%s': %s", schedule_name, ex)
            raise
        return True

    # ------------------------------------------------------------------
    # Lifecycle actions
    # ------------------------------------------------------------------

    async def delete_async(
        self, schedule_name: str, id_postfix: Optional[str] = None
    ) -> None:
        """Delete the schedule. Raises ``ScheduleNotFoundError`` if absent."""
        schedule = await self.get_async(schedule_name, id_postfix)
        await schedule.delete_async()

    async def pause_async(
        self,
        schedule_name: str,
        id_postfix: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """Pause a schedule by name. Raises ``ScheduleNotFoundError`` if absent."""
        schedule = await self.get_async(schedule_name, id_postfix)
        await schedule.pause_async(note)

    async def unpause_async(
        self,
        schedule_name: str,
        id_postfix: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """Unpause a schedule by name."""
        schedule = await self.get_async(schedule_name, id_postfix)
        await schedule.unpause_async(note)

    async def trigger_async(
        self, schedule_name: str, id_postfix: Optional[str] = None
    ) -> None:
        """Trigger an immediate execution of a schedule by name."""
        schedule = await self.get_async(schedule_name, id_postfix)
        await schedule.trigger_async()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def get_temporal_client_async(self) -> Optional["Client"]:
        """Return the current Temporal client (may be ``None`` if not connected)."""
        return await self._get_temporal_client()

    async def _require_client(self) -> "Client":
        client = await self._get_temporal_client()
        if client is None:
            raise RuntimeError(
                "Temporal client is not initialized. Connect the platform "
                "before using the schedules API."
            )
        return client

    def _effective_tenant_id(self) -> str:
        """Resolve tenant ID for schedule ID construction."""
        if self._system_scoped:
            tenant_id = XiansContext.get_tenant_id()
            if not tenant_id:
                raise RuntimeError(
                    "System-scoped agent requires a workflow/activity context "
                    "to resolve the tenant ID for schedule operations."
                )
            return tenant_id
        if not self._tenant_id:
            raise RuntimeError(
                "Tenant-scoped agent has no tenant ID configured. Configure "
                "XiansOptions with a valid API key."
            )
        return self._tenant_id


__all__ = ["ScheduleCollection"]
