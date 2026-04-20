"""Fluent helper methods attached to :class:`ScheduleBuilder`.

Mirrors C# ``ScheduleExtensions``. Provides high-level shorthand methods for
time-based, interval-based, and overlap-policy configuration.

This module monkey-patches :class:`ScheduleBuilder` at import time so the
helper methods are available directly on the fluent chain, just like C#
extension methods.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from .schedule_builder import ScheduleBuilder


# ---------------------------------------------------------------------------
# Time-based schedule patterns
# ---------------------------------------------------------------------------

def _daily(
    self: ScheduleBuilder, hour: int, minute: int = 0, timezone: Optional[str] = None
) -> ScheduleBuilder:
    """Create a daily schedule at the given hour and minute."""
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")
    return self.with_cron_schedule(f"{minute} {hour} * * *", timezone)


def _weekly(
    self: ScheduleBuilder,
    day_of_week: int,
    hour: int,
    minute: int = 0,
    timezone: Optional[str] = None,
) -> ScheduleBuilder:
    """Create a weekly schedule on the given day of week (0=Sunday … 6=Saturday)."""
    if day_of_week < 0 or day_of_week > 6:
        raise ValueError("day_of_week must be between 0 (Sunday) and 6 (Saturday)")
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")
    return self.with_cron_schedule(f"{minute} {hour} * * {day_of_week}", timezone)


def _monthly(
    self: ScheduleBuilder,
    day_of_month: int,
    hour: int,
    minute: int = 0,
    timezone: Optional[str] = None,
) -> ScheduleBuilder:
    """Create a monthly schedule on a specific day of month."""
    if day_of_month < 1 or day_of_month > 31:
        raise ValueError("day_of_month must be between 1 and 31")
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")
    return self.with_cron_schedule(f"{minute} {hour} {day_of_month} * *", timezone)


def _hourly(self: ScheduleBuilder, minute: int = 0) -> ScheduleBuilder:
    """Create an hourly schedule at a specific minute."""
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")
    return self.with_cron_schedule(f"{minute} * * * *")


def _weekdays(
    self: ScheduleBuilder, hour: int, minute: int = 0, timezone: Optional[str] = None
) -> ScheduleBuilder:
    """Create a Monday–Friday schedule at the given time."""
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")
    return self.with_cron_schedule(f"{minute} {hour} * * 1-5", timezone)


# ---------------------------------------------------------------------------
# Interval-based schedule patterns
# ---------------------------------------------------------------------------

def _every_minutes(self: ScheduleBuilder, minutes: int) -> ScheduleBuilder:
    """Create a schedule for every N minutes."""
    if minutes <= 0:
        raise ValueError("minutes must be greater than 0")
    return self.with_interval_schedule(timedelta(minutes=minutes))


def _every_hours(self: ScheduleBuilder, hours: int) -> ScheduleBuilder:
    """Create a schedule for every N hours."""
    if hours <= 0:
        raise ValueError("hours must be greater than 0")
    return self.with_interval_schedule(timedelta(hours=hours))


def _every_seconds(self: ScheduleBuilder, seconds: int) -> ScheduleBuilder:
    """Create a schedule for every N seconds."""
    if seconds <= 0:
        raise ValueError("seconds must be greater than 0")
    return self.with_interval_schedule(timedelta(seconds=seconds))


def _every_days(
    self: ScheduleBuilder,
    days: int,
    hour: int = 0,
    minute: int = 0,
    timezone: Optional[str] = None,
) -> ScheduleBuilder:
    """Create a schedule for every N days.

    When ``days == 1`` and ``hour``/``minute`` are supplied, this is equivalent
    to :meth:`daily`. For multi-day intervals the ``hour``/``minute`` arguments
    are ignored and a pure interval schedule is produced.
    """
    if days <= 0:
        raise ValueError("days must be greater than 0")
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")

    if days == 1:
        return self.daily(hour=hour, minute=minute, timezone=timezone)
    return self.with_interval_schedule(timedelta(days=days))


# ---------------------------------------------------------------------------
# Overlap policy shortcuts
# ---------------------------------------------------------------------------

def _allow_overlap(self: ScheduleBuilder) -> ScheduleBuilder:
    """Allow all concurrent executions (no skipping or queuing)."""
    from temporalio.client import ScheduleOverlapPolicy

    return self.with_overlap_policy(ScheduleOverlapPolicy.ALLOW_ALL)


def _skip_if_running(self: ScheduleBuilder) -> ScheduleBuilder:
    """Skip any new execution while a previous one is still running (recommended)."""
    from temporalio.client import ScheduleOverlapPolicy

    return self.with_overlap_policy(ScheduleOverlapPolicy.SKIP)


def _buffer_one(self: ScheduleBuilder) -> ScheduleBuilder:
    """Queue at most one pending execution while another is running."""
    from temporalio.client import ScheduleOverlapPolicy

    return self.with_overlap_policy(ScheduleOverlapPolicy.BUFFER_ONE)


def _cancel_other(self: ScheduleBuilder) -> ScheduleBuilder:
    """Cancel a running execution before starting a new one."""
    from temporalio.client import ScheduleOverlapPolicy

    return self.with_overlap_policy(ScheduleOverlapPolicy.CANCEL_OTHER)


def _terminate_other(self: ScheduleBuilder) -> ScheduleBuilder:
    """Terminate a running execution before starting a new one (use sparingly)."""
    from temporalio.client import ScheduleOverlapPolicy

    return self.with_overlap_policy(ScheduleOverlapPolicy.TERMINATE_OTHER)


# Attach as methods so callers can chain `.daily(...)` etc.
ScheduleBuilder.daily = _daily  # type: ignore[attr-defined]
ScheduleBuilder.weekly = _weekly  # type: ignore[attr-defined]
ScheduleBuilder.monthly = _monthly  # type: ignore[attr-defined]
ScheduleBuilder.hourly = _hourly  # type: ignore[attr-defined]
ScheduleBuilder.weekdays = _weekdays  # type: ignore[attr-defined]
ScheduleBuilder.every_minutes = _every_minutes  # type: ignore[attr-defined]
ScheduleBuilder.every_hours = _every_hours  # type: ignore[attr-defined]
ScheduleBuilder.every_seconds = _every_seconds  # type: ignore[attr-defined]
ScheduleBuilder.every_days = _every_days  # type: ignore[attr-defined]
ScheduleBuilder.allow_overlap = _allow_overlap  # type: ignore[attr-defined]
ScheduleBuilder.skip_if_running = _skip_if_running  # type: ignore[attr-defined]
ScheduleBuilder.buffer_one = _buffer_one  # type: ignore[attr-defined]
ScheduleBuilder.cancel_other = _cancel_other  # type: ignore[attr-defined]
ScheduleBuilder.terminate_other = _terminate_other  # type: ignore[attr-defined]


__all__: list[str] = []
