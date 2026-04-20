"""XiansSchedule - thin wrapper around Temporal's ``ScheduleHandle``.

Mirrors C# ``Xians.Lib.Agents.Scheduling.XiansSchedule``. Provides a friendly
surface for describing, pausing, unpausing, triggering, updating, deleting and
back-filling a schedule.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Iterable

if TYPE_CHECKING:
    from temporalio.client import (
        ScheduleBackfill,
        ScheduleDescription,
        ScheduleHandle,
        ScheduleUpdate,
        ScheduleUpdateInput,
    )

logger = logging.getLogger(__name__)


class XiansSchedule:
    """Wrapper around a Temporal :class:`ScheduleHandle`.

    Instances are produced by :class:`ScheduleBuilder` / :class:`ScheduleCollection`
    and expose a small, async, idiomatic surface for schedule lifecycle
    operations.
    """

    def __init__(self, handle: "ScheduleHandle") -> None:
        if handle is None:
            raise ValueError("handle cannot be None")
        self._handle = handle

    @property
    def id(self) -> str:
        """Full Temporal schedule ID."""
        return self._handle.id

    def get_handle(self) -> "ScheduleHandle":
        """Return the underlying Temporal handle for advanced scenarios.

        Mirrors C# ``XiansSchedule.GetHandle``.
        """
        return self._handle

    async def describe_async(self) -> "ScheduleDescription":
        """Return current schedule information (next run times, recent actions)."""
        try:
            return await self._handle.describe()
        except Exception as ex:
            logger.error("Failed to describe schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to describe schedule '{self.id}'") from ex

    async def pause_async(self, note: str | None = None) -> None:
        """Pause the schedule. Prevents future workflow executions."""
        try:
            await self._handle.pause(note=note)
            logger.debug("Schedule '%s' paused. Note: %s", self.id, note or "None")
        except Exception as ex:
            logger.error("Failed to pause schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to pause schedule '{self.id}'") from ex

    async def unpause_async(self, note: str | None = None) -> None:
        """Resume a paused schedule."""
        try:
            await self._handle.unpause(note=note)
            logger.debug("Schedule '%s' unpaused. Note: %s", self.id, note or "None")
        except Exception as ex:
            logger.error("Failed to unpause schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to unpause schedule '{self.id}'") from ex

    async def trigger_async(self) -> None:
        """Trigger an immediate execution of the scheduled workflow."""
        try:
            await self._handle.trigger()
            logger.debug("Schedule '%s' triggered manually", self.id)
        except Exception as ex:
            logger.error("Failed to trigger schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to trigger schedule '{self.id}'") from ex

    async def update_async(
        self,
        updater: Callable[["ScheduleUpdateInput"], "ScheduleUpdate"],
    ) -> None:
        """Update the schedule configuration.

        Accepts a callable mirroring Temporal's update semantics: it receives
        the current :class:`ScheduleUpdateInput` and must return a
        :class:`ScheduleUpdate`. Mirrors C# ``XiansSchedule.UpdateAsync``.
        """
        try:
            await self._handle.update(updater)
            logger.debug("Schedule '%s' updated successfully", self.id)
        except Exception as ex:
            logger.error("Failed to update schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to update schedule '{self.id}'") from ex

    async def delete_async(self) -> None:
        """Delete the schedule. Does not affect workflows already started."""
        try:
            await self._handle.delete()
            logger.debug("Schedule '%s' deleted successfully", self.id)
        except Exception as ex:
            logger.error("Failed to delete schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to delete schedule '{self.id}'") from ex

    async def backfill_async(self, backfills: Iterable["ScheduleBackfill"]) -> None:
        """Backfill the schedule by executing actions for past time ranges."""
        backfill_list = list(backfills)
        try:
            await self._handle.backfill(backfill_list)
            logger.debug(
                "Schedule '%s' backfilled for %d time range(s)",
                self.id,
                len(backfill_list),
            )
        except Exception as ex:
            logger.error("Failed to backfill schedule '%s': %s", self.id, ex)
            raise RuntimeError(f"Failed to backfill schedule '{self.id}'") from ex


__all__ = ["XiansSchedule"]
