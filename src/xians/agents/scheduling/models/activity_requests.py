"""Serializable request payloads for schedule activities.

Mirrors C# ``Xians.Lib.Temporal.Workflows.Scheduling.Models.ActivityRequests``.
Dataclasses here are passed between a Temporal workflow and its activities so
that schedule creation and management can happen outside the deterministic
workflow loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CreateCronScheduleRequest:
    """Request payload for creating a cron-based schedule via activity."""

    schedule_name: str
    cron_expression: str
    workflow_type: str
    workflow_input: list[Any] = field(default_factory=list)
    timezone: Optional[str] = None
    id_postfix: Optional[str] = None
    search_attributes: Optional[dict[str, Any]] = None


@dataclass
class CreateIntervalScheduleRequest:
    """Request payload for creating an interval-based schedule via activity."""

    schedule_name: str
    workflow_type: str
    # seconds to keep it JSON-serializable (Temporal Python activities serialize
    # timedelta across workflow/activity boundaries automatically, but using a
    # plain number removes any ambiguity when invoked from non-temporal tests).
    interval_seconds: float = 0.0
    workflow_input: list[Any] = field(default_factory=list)
    id_postfix: Optional[str] = None
    search_attributes: Optional[dict[str, Any]] = None


@dataclass
class ScheduleExistsRequest:
    """Request payload for checking whether a schedule exists."""

    schedule_name: str
    id_postfix: Optional[str] = None


@dataclass
class DeleteScheduleRequest:
    """Request payload for deleting a schedule."""

    schedule_name: str
    id_postfix: Optional[str] = None


@dataclass
class PauseScheduleRequest:
    """Request payload for pausing a schedule."""

    schedule_name: str
    id_postfix: Optional[str] = None
    note: Optional[str] = None


@dataclass
class ResumeScheduleRequest:
    """Request payload for resuming (unpausing) a schedule."""

    schedule_name: str
    id_postfix: Optional[str] = None
    note: Optional[str] = None


@dataclass
class TriggerScheduleRequest:
    """Request payload for triggering an immediate schedule execution."""

    schedule_name: str
    id_postfix: Optional[str] = None


__all__ = [
    "CreateCronScheduleRequest",
    "CreateIntervalScheduleRequest",
    "ScheduleExistsRequest",
    "DeleteScheduleRequest",
    "PauseScheduleRequest",
    "ResumeScheduleRequest",
    "TriggerScheduleRequest",
]
