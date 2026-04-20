"""Fluent builder for creating scheduled workflow executions.

Mirrors C# ``Xians.Lib.Agents.Scheduling.ScheduleBuilder``. Provides:

- Spec helpers: :meth:`with_cron_schedule`, :meth:`with_interval_schedule`,
  :meth:`with_calendar_schedule`, :meth:`with_schedule_spec`
- Extension helpers (via :mod:`schedule_extensions`):
  ``daily``, ``hourly``, ``weekly``, ``monthly``, ``weekdays``,
  ``every_seconds``, ``every_minutes``, ``every_hours``, ``every_days``,
  ``skip_if_running``, ``allow_overlap``, ``buffer_one``,
  ``cancel_other``, ``terminate_other``
- Configuration: :meth:`with_input`, :meth:`with_memo`,
  :meth:`with_typed_search_attributes`, :meth:`with_retry_policy`,
  :meth:`with_timeout`, :meth:`with_schedule_policy`,
  :meth:`with_overlap_policy`, :meth:`start_paused`
- Creation: :meth:`create_async` (strict), :meth:`create_if_not_exists_async`
  (idempotent), :meth:`recreate_async` (replace).

When called from within a Temporal workflow, creation is dispatched to an
activity so the workflow stays deterministic. Outside workflows it calls the
Temporal client directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from ..core.xians_context import XiansContext
from .models.activity_requests import (
    CreateCronScheduleRequest,
    CreateIntervalScheduleRequest,
)
from .models.exceptions import (
    InvalidScheduleSpecError,
    ScheduleAlreadyExistsError,
)
from .schedule_id_helper import ScheduleIdHelper
from .xians_schedule import XiansSchedule

if TYPE_CHECKING:
    from temporalio.client import (
        Client,
        Schedule,
        ScheduleOverlapPolicy,
        SchedulePolicy,
        ScheduleSpec,
        ScheduleState,
    )
    from temporalio.common import RetryPolicy

    from .schedule_collection import ScheduleCollection

logger = logging.getLogger(__name__)

# Default activity execution options used when dispatching schedule creation
# from inside a workflow.  Matches C# ScheduleActivityOptions.GetStandardOptions.
_ACTIVITY_START_TO_CLOSE = timedelta(minutes=2)


@dataclass
class _PendingScheduleSpec:
    """Internal spec holder before the temporalio objects are created.

    We keep a neutral representation so the builder can be inspected (and unit
    tested) without requiring the temporalio runtime to be active.
    """

    cron_expression: Optional[str] = None
    interval: Optional[timedelta] = None
    interval_offset: Optional[timedelta] = None
    calendar_time: Optional[datetime] = None
    timezone: Optional[str] = None


# Standard keyword search attributes that every Xians-managed schedule (and its
# scheduled workflow executions) carries so operators can filter schedules by
# tenant, agent, user, or run-scoping postfix in the Temporal UI.  Mirrors C#
# ``WorkflowMetadataResolver.BuildSearchAttributes`` / ``StandardMetadataKeys``.
_STANDARD_SEARCH_ATTR_KEYS = ("tenantId", "agent", "userId", "idPostfix")


class ScheduleBuilder:
    """Fluent builder for scheduled workflow executions.

    Instances are created via :meth:`ScheduleCollection.create`.  The builder
    is mutated by chained configuration calls and finalized by one of the
    ``*_async`` creation methods.
    """

    def __init__(
        self,
        *,
        schedule_name: str,
        agent_name: str,
        system_scoped: bool,
        tenant_id: Optional[str],
        workflow_type: str,
        collection: "ScheduleCollection",
        id_postfix: Optional[str] = None,
    ) -> None:
        if not schedule_name:
            raise ValueError("schedule_name cannot be empty")
        if not workflow_type:
            raise ValueError("workflow_type cannot be empty")
        self._schedule_name = schedule_name
        self._agent_name = agent_name
        self._system_scoped = system_scoped
        self._configured_tenant_id = tenant_id
        self._workflow_type = workflow_type
        self._collection = collection

        # Use an empty string for _id_postfix when not specified so
        # create_if_not_exists_async yields one schedule per tenant:agent:scheduleName.
        # Pass an explicit id_postfix when you need run-scoped schedules.
        self._id_postfix = id_postfix if id_postfix is not None else self._resolve_effective_id_postfix()

        self._pending_spec: Optional[_PendingScheduleSpec] = None
        self._external_spec: Optional["ScheduleSpec"] = None
        self._workflow_args: list[Any] = []
        self._workflow_memo: Optional[dict[str, Any]] = None
        self._typed_search_attributes: Optional[Any] = None
        self._retry_policy: Optional["RetryPolicy"] = None
        self._timeout: Optional[timedelta] = None
        self._schedule_policy: Optional["SchedulePolicy"] = None
        self._schedule_state: Optional["ScheduleState"] = None

    # ------------------------------------------------------------------
    # Spec helpers
    # ------------------------------------------------------------------

    def with_cron_schedule(
        self, cron_expression: str, timezone: Optional[str] = None
    ) -> "ScheduleBuilder":
        """Set a cron-based schedule using a standard 5-field cron expression.

        Format: ``{minute} {hour} {day-of-month} {month} {day-of-week}``.
        """
        if not cron_expression or not cron_expression.strip():
            raise ValueError("Cron expression cannot be null or empty")
        self._pending_spec = _PendingScheduleSpec(
            cron_expression=cron_expression, timezone=timezone
        )
        self._external_spec = None
        return self

    def with_interval_schedule(
        self, interval: timedelta, offset: Optional[timedelta] = None
    ) -> "ScheduleBuilder":
        """Set an interval-based schedule."""
        if interval is None or interval.total_seconds() <= 0:
            raise ValueError("Interval must be greater than zero")
        self._pending_spec = _PendingScheduleSpec(
            interval=interval,
            interval_offset=offset,
        )
        self._external_spec = None
        return self

    def with_calendar_schedule(
        self, scheduled_time: datetime, timezone: Optional[str] = None
    ) -> "ScheduleBuilder":
        """Set a calendar-based schedule for a specific date/time."""
        if scheduled_time is None:
            raise ValueError("scheduled_time cannot be None")
        self._pending_spec = _PendingScheduleSpec(
            calendar_time=scheduled_time,
            timezone=timezone,
        )
        self._external_spec = None
        return self

    def with_schedule_spec(self, spec: "ScheduleSpec") -> "ScheduleBuilder":
        """Set a custom, fully-formed ``temporalio.client.ScheduleSpec``."""
        if spec is None:
            raise ValueError("spec cannot be None")
        self._external_spec = spec
        self._pending_spec = None
        return self

    # ------------------------------------------------------------------
    # Workflow configuration
    # ------------------------------------------------------------------

    def with_input(self, *args: Any) -> "ScheduleBuilder":
        """Set positional arguments that will be passed to each execution."""
        self._workflow_args = list(args)
        return self

    def with_memo(self, memo: dict[str, Any]) -> "ScheduleBuilder":
        """Set the workflow memo for additional metadata."""
        if memo is None:
            raise ValueError("memo cannot be None")
        self._workflow_memo = dict(memo)
        return self

    def with_typed_search_attributes(self, search_attributes: Any) -> "ScheduleBuilder":
        """Set a ``temporalio.common.TypedSearchAttributes`` collection."""
        self._typed_search_attributes = search_attributes
        return self

    def with_retry_policy(self, retry_policy: "RetryPolicy") -> "ScheduleBuilder":
        """Set a retry policy for the scheduled workflow executions."""
        if retry_policy is None:
            raise ValueError("retry_policy cannot be None")
        self._retry_policy = retry_policy
        return self

    def with_timeout(self, timeout: timedelta) -> "ScheduleBuilder":
        """Set the run timeout for scheduled workflow executions."""
        if timeout is None or timeout.total_seconds() <= 0:
            raise ValueError("Timeout must be greater than zero")
        self._timeout = timeout
        return self

    def with_schedule_policy(self, policy: "SchedulePolicy") -> "ScheduleBuilder":
        """Set the full schedule policy (overlap, catch-up, pause-on-failure)."""
        if policy is None:
            raise ValueError("policy cannot be None")
        self._schedule_policy = policy
        return self

    def with_overlap_policy(
        self, overlap_policy: "ScheduleOverlapPolicy"
    ) -> "ScheduleBuilder":
        """Shorthand for setting only the overlap portion of the schedule policy."""
        from temporalio.client import SchedulePolicy

        self._schedule_policy = SchedulePolicy(overlap=overlap_policy)
        return self

    def start_paused(
        self, paused: bool = True, note: Optional[str] = None
    ) -> "ScheduleBuilder":
        """Create the schedule in a paused state (defaults to paused=True)."""
        from temporalio.client import ScheduleState

        self._schedule_state = ScheduleState(paused=paused, note=note)
        return self

    # ------------------------------------------------------------------
    # Creation methods
    # ------------------------------------------------------------------

    async def create_async(self) -> XiansSchedule:
        """Create a new schedule. Fails if a schedule with the same ID exists.

        Raises:
            InvalidScheduleSpecError: when no spec has been configured.
            ScheduleAlreadyExistsError: when a schedule with the derived ID
                already exists.
        """
        self._ensure_spec_configured()
        if self._is_in_workflow_context():
            return await self._create_via_activities(idempotent=False)
        return await self._create_via_temporal_client(check_exists=False)

    async def create_if_not_exists_async(self) -> XiansSchedule:
        """Create the schedule if it does not exist. Idempotent.

        Returns the existing schedule if one is already present.
        """
        self._ensure_spec_configured()
        if self._is_in_workflow_context():
            return await self._create_via_activities(idempotent=True)
        return await self._create_via_temporal_client(check_exists=True)

    async def recreate_async(self) -> XiansSchedule:
        """Delete any existing schedule with the same ID, then create a new one.

        Useful when updating a schedule configuration.
        """
        self._ensure_spec_configured()
        try:
            await self._collection.delete_async(
                self._schedule_name, id_postfix=self._id_postfix
            )
        except Exception as ex:  # pragma: no cover - defensive
            logger.debug(
                "recreate_async: no existing schedule to delete for '%s' (%s)",
                self._schedule_name,
                ex,
            )
        return await self.create_async()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_spec_configured(self) -> None:
        if self._pending_spec is None and self._external_spec is None:
            raise InvalidScheduleSpecError(
                "Schedule specification is required. Use with_cron_schedule, "
                "with_interval_schedule, with_calendar_schedule, or "
                "with_schedule_spec."
            )

    @staticmethod
    def _is_in_workflow_context() -> bool:
        """True when running inside a Temporal workflow (not an activity)."""
        return XiansContext.in_workflow()

    def _resolve_effective_id_postfix(self) -> Optional[str]:
        """Return the idPostfix to use for schedule operations.

        Matches C# ``GetEffectiveIdPostfixForSchedule``:
        - Explicit value (set via constructor) wins when non-empty.
        - Otherwise, when running inside a workflow/activity, try to resolve
          from the workflow ID/metadata.
        - Fallback: ``None``.
        """
        if XiansContext.in_workflow_or_activity():
            from_context = XiansContext.safe_id_postfix()
            if from_context:
                return from_context
        return None

    def _effective_tenant_id(self) -> str:
        """Resolve the tenant ID the schedule will be scoped under.

        For system-scoped agents the tenant is pulled from the workflow
        context (must be inside a workflow/activity).  For tenant-scoped
        agents the registered tenant ID is used.
        """
        if self._system_scoped:
            tenant_id = XiansContext.get_tenant_id()
            if not tenant_id:
                raise RuntimeError(
                    "System-scoped agent requires a workflow/activity context "
                    "to resolve the tenant ID for schedule operations."
                )
            return tenant_id
        if not self._configured_tenant_id:
            raise RuntimeError(
                "Tenant-scoped agent must have a valid tenant ID. "
                "XiansOptions not properly configured."
            )
        return self._configured_tenant_id

    def _build_full_schedule_id(self) -> str:
        return ScheduleIdHelper.build_full_schedule_id(
            self._effective_tenant_id(),
            self._agent_name,
            self._id_postfix,
            self._schedule_name,
        )

    def _build_temporal_schedule_spec(self) -> "ScheduleSpec":
        """Translate the pending spec into a temporalio ``ScheduleSpec``."""
        if self._external_spec is not None:
            return self._external_spec

        assert self._pending_spec is not None  # guarded by _ensure_spec_configured
        from temporalio.client import (
            ScheduleCalendarSpec,
            ScheduleIntervalSpec,
            ScheduleRange,
            ScheduleSpec,
        )

        pending = self._pending_spec
        if pending.cron_expression:
            return ScheduleSpec(
                cron_expressions=[pending.cron_expression],
                time_zone_name=pending.timezone,
            )

        if pending.interval is not None:
            kwargs: dict[str, Any] = {"every": pending.interval}
            if pending.interval_offset is not None:
                kwargs["offset"] = pending.interval_offset
            return ScheduleSpec(intervals=[ScheduleIntervalSpec(**kwargs)])

        if pending.calendar_time is not None:
            dt = pending.calendar_time
            return ScheduleSpec(
                calendars=[
                    ScheduleCalendarSpec(
                        year=[ScheduleRange(dt.year)],
                        month=[ScheduleRange(dt.month)],
                        day_of_month=[ScheduleRange(dt.day)],
                        hour=[ScheduleRange(dt.hour)],
                        minute=[ScheduleRange(dt.minute)],
                        second=[ScheduleRange(dt.second)],
                    )
                ],
                time_zone_name=pending.timezone,
            )

        raise InvalidScheduleSpecError("Pending schedule spec is incomplete")

    def _build_standard_search_attributes(self, tenant_id: str) -> Any:
        """Build the standard ``TypedSearchAttributes`` carried by every schedule.

        Keys (all ``Keyword``): ``tenantId``, ``agent``, ``userId``, ``idPostfix``.

        Mirrors C# ``WorkflowMetadataResolver.BuildSearchAttributes``. These
        attributes **must be pre-registered** on the Temporal namespace (the
        same way they are for the C# library).  If they are not registered,
        Temporal will reject the ``CreateSchedule`` call with an error that
        includes the missing key name.
        """
        from temporalio.common import (
            SearchAttributeKey,
            SearchAttributePair,
            TypedSearchAttributes,
        )

        user_id = XiansContext.safe_participant_id() or ""
        values: dict[str, str] = {
            "tenantId": tenant_id,
            "agent": self._agent_name,
            "userId": user_id,
            "idPostfix": self._id_postfix or "",
        }
        pairs = [
            SearchAttributePair(SearchAttributeKey.for_keyword(key), value)
            for key, value in values.items()
        ]
        return TypedSearchAttributes(search_attributes=pairs)

    def _resolve_effective_search_attributes(self, tenant_id: str) -> Any:
        """Return the ``TypedSearchAttributes`` to attach to the schedule.

        Priority (matches C# ``GetEffectiveSearchAttributesForScheduleAsync``):

        1. User-provided via :meth:`with_typed_search_attributes` — merged with
           the 4 standard keys so those are always present.
        2. The 4 standard keys built from the current context.
        """
        standard = self._build_standard_search_attributes(tenant_id)

        if self._typed_search_attributes is None:
            return standard

        # Merge: user-provided wins on conflicts, standard keys fill the gaps.
        from temporalio.common import TypedSearchAttributes

        try:
            user_pairs = list(
                getattr(self._typed_search_attributes, "search_attributes", [])
            )
        except Exception:
            user_pairs = []
        user_keys = {
            getattr(pair.key, "name", None) for pair in user_pairs
        }
        merged = list(user_pairs)
        for pair in standard.search_attributes:
            if getattr(pair.key, "name", None) not in user_keys:
                merged.append(pair)
        return TypedSearchAttributes(search_attributes=merged)

    def _build_memo(self, tenant_id: str) -> dict[str, Any]:
        """Build memo dict attached to every scheduled workflow execution.

        Mirrors C# ``ScheduleBuilder.GetMemo`` (system-required metadata merged
        with user-provided memo).  Values cannot be ``None`` — Temporal rejects
        null memo entries — so we fall back to empty strings.
        """
        user_id = XiansContext.safe_participant_id() or ""
        memo: dict[str, Any] = {
            "tenantId": tenant_id,
            "agent": self._agent_name,
            "userId": user_id,
            "idPostfix": self._id_postfix or "",
            "systemScoped": self._system_scoped,
        }
        if self._workflow_memo:
            memo.update(self._workflow_memo)
        return memo

    async def _get_temporal_client(self) -> "Client":
        client = await self._collection.get_temporal_client_async()
        if client is None:
            raise RuntimeError(
                "Temporal client is not initialized. Connect the platform "
                "before creating or managing schedules."
            )
        return client

    async def _create_via_temporal_client(self, check_exists: bool) -> XiansSchedule:
        """Create the schedule directly via the Temporal client."""
        from temporalio.client import (
            Schedule,
            ScheduleActionStartWorkflow,
            ScheduleAlreadyRunningError,
            SchedulePolicy,
            ScheduleState,
        )

        client = await self._get_temporal_client()
        full_schedule_id = self._build_full_schedule_id()
        tenant_id = self._effective_tenant_id()

        # Optional idempotency: if schedule already exists, return a wrapper.
        if check_exists:
            existing = await self._try_get_existing_schedule(client, full_schedule_id)
            if existing is not None:
                return existing

        from ...temporal_workflows.v1.worker_runner import build_task_queue_name

        task_queue = build_task_queue_name(
            workflow_type=self._workflow_type,
            system_scoped=self._system_scoped,
            tenant_id=tenant_id if not self._system_scoped else None,
        )
        workflow_id = ScheduleIdHelper.build_full_workflow_id(
            tenant_id, self._workflow_type, self._id_postfix or ""
        )

        # Always attach the 4 standard keyword search attributes (tenantId,
        # agent, userId, idPostfix) — merged with any user-provided ones.
        # Matches C# ``GetEffectiveSearchAttributesForScheduleAsync``.
        search_attributes = self._resolve_effective_search_attributes(tenant_id)
        schedule_spec = self._build_temporal_schedule_spec()
        schedule_action = ScheduleActionStartWorkflow(
            self._workflow_type,
            args=self._workflow_args,
            id=workflow_id,
            task_queue=task_queue,
            retry_policy=self._retry_policy,
            run_timeout=self._timeout,
            typed_search_attributes=search_attributes,
            memo=self._build_memo(tenant_id),
        )

        schedule = Schedule(
            action=schedule_action,
            spec=schedule_spec,
            policy=self._schedule_policy or SchedulePolicy(),
            state=self._schedule_state or ScheduleState(),
        )

        try:
            # Pass search_attributes on the schedule itself too (not just the
            # workflow action).  Mirrors C# which issues a follow-up
            # `handle.UpdateAsync` after creation — Python SDK lets us do it in
            # one call.
            handle = await client.create_schedule(
                full_schedule_id,
                schedule,
                search_attributes=search_attributes,
            )
        except ScheduleAlreadyRunningError as ex:
            logger.error("Schedule '%s' already exists", self._schedule_name)
            raise ScheduleAlreadyExistsError(self._schedule_name, cause=ex) from ex
        except Exception as ex:
            logger.error("Failed to create schedule '%s': %s", self._schedule_name, ex)
            raise

        logger.debug(
            "Schedule '%s' created successfully. Agent='%s', SystemScoped=%s, TenantId=%s",
            full_schedule_id,
            self._agent_name,
            self._system_scoped,
            tenant_id,
        )
        return XiansSchedule(handle)

    @staticmethod
    async def _try_get_existing_schedule(
        client: "Client", full_schedule_id: str
    ) -> Optional[XiansSchedule]:
        """Return a wrapper over an existing schedule, or ``None`` if missing."""
        try:
            handle = client.get_schedule_handle(full_schedule_id)
            await handle.describe()
            return XiansSchedule(handle)
        except Exception as ex:
            message = str(ex).lower()
            if "not found" in message or "does not exist" in message:
                return None
            # For any other error, let the caller decide whether to proceed.
            raise

    async def _create_via_activities(self, idempotent: bool) -> XiansSchedule:
        """Dispatch schedule creation to an activity for workflow determinism.

        The activity handles the actual Temporal client interaction, keeping
        the workflow code deterministic.
        """
        from temporalio import workflow

        pending = self._pending_spec
        if pending is None:
            raise InvalidScheduleSpecError(
                "Complex schedule specifications not yet supported in workflow "
                "context. Use cron or interval schedules, or create the "
                "schedule outside the workflow."
            )

        search_attrs = self._serialize_search_attributes()
        effective_id_postfix = self._resolve_effective_id_postfix()
        activity_name = (
            "ScheduleActivities.create_schedule_if_not_exists"
            if pending.cron_expression
            else "ScheduleActivities.create_interval_schedule_if_not_exists"
        )

        if pending.cron_expression:
            request = CreateCronScheduleRequest(
                schedule_name=self._schedule_name,
                cron_expression=pending.cron_expression,
                workflow_type=self._workflow_type,
                workflow_input=list(self._workflow_args),
                timezone=pending.timezone,
                id_postfix=effective_id_postfix,
                search_attributes=search_attrs,
            )
        elif pending.interval is not None:
            request = CreateIntervalScheduleRequest(
                schedule_name=self._schedule_name,
                workflow_type=self._workflow_type,
                interval_seconds=pending.interval.total_seconds(),
                workflow_input=list(self._workflow_args),
                id_postfix=effective_id_postfix,
                search_attributes=search_attrs,
            )
        else:
            raise InvalidScheduleSpecError(
                "Complex schedule specifications not yet supported in workflow "
                "context. Use cron or interval schedules, or create the "
                "schedule outside the workflow."
            )

        await workflow.execute_activity(
            activity_name,
            request,
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE,
        )

        # Return a handle bound to the full schedule ID; Temporal handles are
        # cheap and verified on first use outside the workflow.
        client = await self._get_temporal_client()
        return XiansSchedule(client.get_schedule_handle(self._build_full_schedule_id()))

    def _serialize_search_attributes(self) -> Optional[dict[str, Any]]:
        """Serialize typed search attributes into a plain dict for activities.

        Mirrors C# ``WorkflowMetadataResolver.ExtractToSerializableDictionary``.
        The Python SDK can't deterministically marshal ``TypedSearchAttributes``
        across the workflow/activity boundary, so we drop to a best-effort
        dictionary representation.
        """
        if self._typed_search_attributes is None:
            return None
        # TypedSearchAttributes exposes ``search_attributes`` list of typed pairs.
        try:
            pairs = getattr(self._typed_search_attributes, "search_attributes", [])
            result: dict[str, Any] = {}
            for pair in pairs:
                key = getattr(pair.key, "name", None) if hasattr(pair, "key") else None
                if key is None:
                    continue
                result[key] = pair.value
            return result or None
        except Exception:
            return None


__all__ = ["ScheduleBuilder"]
