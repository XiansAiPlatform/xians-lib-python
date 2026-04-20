"""Scheduling package for Xians agents.

Mirrors C# Xians.Lib.Agents.Scheduling. Provides a fluent API for creating
and managing Temporal-backed scheduled workflow executions.

Public surface:
    ScheduleCollection   - Created automatically on each AgentRegistration
    ScheduleBuilder      - Returned by ScheduleCollection.create()
    XiansSchedule        - Wraps a Temporal ScheduleHandle
    Exceptions           - ScheduleNotFoundError, ScheduleAlreadyExistsError,
                           InvalidScheduleSpecError
"""

from .models.exceptions import (
    InvalidScheduleSpecError,
    ScheduleAlreadyExistsError,
    ScheduleNotFoundError,
)
from .schedule_builder import ScheduleBuilder
from .schedule_collection import ScheduleCollection
from .schedule_id_helper import ScheduleIdHelper
from .xians_schedule import XiansSchedule

__all__ = [
    "InvalidScheduleSpecError",
    "ScheduleAlreadyExistsError",
    "ScheduleNotFoundError",
    "ScheduleBuilder",
    "ScheduleCollection",
    "ScheduleIdHelper",
    "XiansSchedule",
]
