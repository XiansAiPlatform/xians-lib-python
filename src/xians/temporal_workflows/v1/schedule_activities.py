"""Temporal activities that bridge in-workflow schedule operations.

Mirrors C# ``Xians.Lib.Temporal.Workflows.Scheduling.ScheduleActivities``. These
activities are automatically registered with all worker queues so workflows can
create and manage schedules via ``workflow.execute_activity`` while remaining
deterministic.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from temporalio import activity

from ...agents.core.xians_context import XiansContext
from ...agents.scheduling.models.activity_requests import (
    CreateCronScheduleRequest,
    CreateIntervalScheduleRequest,
    DeleteScheduleRequest,
    PauseScheduleRequest,
    ResumeScheduleRequest,
    ScheduleExistsRequest,
    TriggerScheduleRequest,
)
from ...agents.scheduling.models.exceptions import ScheduleNotFoundError

logger = logging.getLogger(__name__)


class ScheduleActivities:
    """Bundle of Temporal activities for schedule lifecycle management."""

    def __init__(self) -> None:
        self._logger = logger

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _current_agent() -> Any:
        """Resolve the current agent via :class:`XiansContext`.

        The agent registry is populated during :meth:`XiansPlatform.initialize`,
        so this is available from any activity running inside a configured
        worker.
        """
        return XiansContext.CurrentAgent

    @staticmethod
    def _rehydrate_search_attributes(serialized: Optional[dict[str, Any]]) -> Any:
        """Convert a serialized attr dict back to ``TypedSearchAttributes``.

        The in-workflow path flattens typed search attributes to a plain dict
        so they can cross the activity boundary (Temporal Python cannot
        serialize ``TypedSearchAttributes`` itself).  Here we rebuild a
        ``Keyword``-typed collection from those values so the schedule still
        receives the user's custom keys.
        """
        if not serialized:
            return None

        from temporalio.common import (
            SearchAttributeKey,
            SearchAttributePair,
            TypedSearchAttributes,
        )

        pairs = [
            SearchAttributePair(SearchAttributeKey.for_keyword(key), str(value))
            for key, value in serialized.items()
            if value is not None
        ]
        if not pairs:
            return None
        return TypedSearchAttributes(search_attributes=pairs)

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    @activity.defn(name="ScheduleActivities.create_schedule_if_not_exists")
    async def create_schedule_if_not_exists(
        self, request: CreateCronScheduleRequest
    ) -> bool:
        """Create a cron schedule if it doesn't already exist. Returns True when a
        new schedule was created, False when one already existed."""
        agent = self._current_agent()
        try:
            if await agent.schedules.exists_async(
                request.schedule_name, request.id_postfix
            ):
                self._logger.debug(
                    "Schedule '%s' already exists, skipping creation",
                    request.schedule_name,
                )
                return False

            builder = (
                agent.schedules.create(
                    request.schedule_name,
                    request.workflow_type,
                    id_postfix=request.id_postfix,
                )
                .with_cron_schedule(request.cron_expression, request.timezone)
                .with_input(*(request.workflow_input or []))
            )
            user_search_attrs = self._rehydrate_search_attributes(
                request.search_attributes
            )
            if user_search_attrs is not None:
                builder = builder.with_typed_search_attributes(user_search_attrs)
            await builder.create_if_not_exists_async()
            self._logger.debug(
                "Successfully created cron schedule '%s' with cron '%s'",
                request.schedule_name,
                request.cron_expression,
            )
            return True
        except Exception as ex:
            self._logger.error(
                "Failed to create schedule '%s': %s", request.schedule_name, ex
            )
            raise

    @activity.defn(name="ScheduleActivities.create_interval_schedule_if_not_exists")
    async def create_interval_schedule_if_not_exists(
        self, request: CreateIntervalScheduleRequest
    ) -> bool:
        """Create an interval schedule if it doesn't already exist."""
        agent = self._current_agent()
        try:
            if await agent.schedules.exists_async(
                request.schedule_name, request.id_postfix
            ):
                self._logger.debug(
                    "Schedule '%s' already exists, skipping creation",
                    request.schedule_name,
                )
                return False

            interval = timedelta(seconds=request.interval_seconds)
            builder = (
                agent.schedules.create(
                    request.schedule_name,
                    request.workflow_type,
                    id_postfix=request.id_postfix,
                )
                .with_interval_schedule(interval)
                .with_input(*(request.workflow_input or []))
            )
            user_search_attrs = self._rehydrate_search_attributes(
                request.search_attributes
            )
            if user_search_attrs is not None:
                builder = builder.with_typed_search_attributes(user_search_attrs)
            await builder.create_if_not_exists_async()
            self._logger.debug(
                "Successfully created interval schedule '%s' with interval %s",
                request.schedule_name,
                interval,
            )
            return True
        except Exception as ex:
            self._logger.error(
                "Failed to create interval schedule '%s': %s",
                request.schedule_name,
                ex,
            )
            raise

    # ------------------------------------------------------------------
    # Lookup / lifecycle
    # ------------------------------------------------------------------

    @activity.defn(name="ScheduleActivities.schedule_exists")
    async def schedule_exists(self, request: ScheduleExistsRequest) -> bool:
        """Return whether a schedule exists for this agent."""
        agent = self._current_agent()
        return await agent.schedules.exists_async(
            request.schedule_name, request.id_postfix
        )

    @activity.defn(name="ScheduleActivities.delete_schedule")
    async def delete_schedule(self, request: DeleteScheduleRequest) -> bool:
        """Delete the schedule. Returns True on success, False if it didn't exist."""
        agent = self._current_agent()
        try:
            await agent.schedules.delete_async(
                request.schedule_name, request.id_postfix
            )
            self._logger.debug(
                "Successfully deleted schedule '%s'", request.schedule_name
            )
            return True
        except ScheduleNotFoundError:
            self._logger.warning(
                "Schedule '%s' not found for deletion", request.schedule_name
            )
            return False
        except Exception as ex:
            self._logger.error(
                "Failed to delete schedule '%s': %s", request.schedule_name, ex
            )
            raise

    @activity.defn(name="ScheduleActivities.pause_schedule")
    async def pause_schedule(self, request: PauseScheduleRequest) -> None:
        """Pause a schedule by name."""
        agent = self._current_agent()
        try:
            await agent.schedules.pause_async(
                request.schedule_name, request.id_postfix, note=request.note
            )
            self._logger.debug(
                "Successfully paused schedule '%s'", request.schedule_name
            )
        except Exception as ex:
            self._logger.error(
                "Failed to pause schedule '%s': %s", request.schedule_name, ex
            )
            raise

    @activity.defn(name="ScheduleActivities.resume_schedule")
    async def resume_schedule(self, request: ResumeScheduleRequest) -> None:
        """Resume (unpause) a schedule by name."""
        agent = self._current_agent()
        try:
            await agent.schedules.unpause_async(
                request.schedule_name, request.id_postfix, note=request.note
            )
            self._logger.debug(
                "Successfully resumed schedule '%s'", request.schedule_name
            )
        except Exception as ex:
            self._logger.error(
                "Failed to resume schedule '%s': %s", request.schedule_name, ex
            )
            raise

    @activity.defn(name="ScheduleActivities.trigger_schedule")
    async def trigger_schedule(self, request: TriggerScheduleRequest) -> None:
        """Trigger an immediate execution of a schedule by name."""
        agent = self._current_agent()
        try:
            await agent.schedules.trigger_async(
                request.schedule_name, request.id_postfix
            )
            self._logger.debug(
                "Successfully triggered schedule '%s'", request.schedule_name
            )
        except Exception as ex:
            self._logger.error(
                "Failed to trigger schedule '%s': %s", request.schedule_name, ex
            )
            raise


__all__ = ["ScheduleActivities"]
