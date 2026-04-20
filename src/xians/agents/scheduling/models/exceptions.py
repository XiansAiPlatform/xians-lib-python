"""Scheduling-specific exceptions. Mirrors C# models in
`Xians.Lib.Agents.Scheduling.Models`.
"""

from __future__ import annotations

from ....exceptions.v1.errors import XiansError


class ScheduleAlreadyExistsError(XiansError):
    """Raised when attempting to create a schedule that already exists.

    Mirrors C# ``ScheduleAlreadyExistsException``.
    """

    def __init__(self, schedule_id: str, cause: Exception | None = None) -> None:
        super().__init__(f"Schedule '{schedule_id}' already exists.", cause=cause)
        self.schedule_id = schedule_id


class ScheduleNotFoundError(XiansError):
    """Raised when a schedule is not found.

    Mirrors C# ``ScheduleNotFoundException``.
    """

    def __init__(self, schedule_id: str, cause: Exception | None = None) -> None:
        super().__init__(f"Schedule '{schedule_id}' not found.", cause=cause)
        self.schedule_id = schedule_id


class InvalidScheduleSpecError(XiansError):
    """Raised when a schedule specification is invalid.

    Mirrors C# ``InvalidScheduleSpecException``.
    """


__all__ = [
    "ScheduleAlreadyExistsError",
    "ScheduleNotFoundError",
    "InvalidScheduleSpecError",
]
