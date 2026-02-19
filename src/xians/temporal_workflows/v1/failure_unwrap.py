import re
from typing import Any

try:
    from temporalio.exceptions import (
        ActivityError,
        ApplicationError,
        FailureError,
        WorkflowFailureError,
    )

    TEMPORAL_EXCEPTION_TYPES = (
        ActivityError,
        ApplicationError,
        WorkflowFailureError,
        FailureError,
    )
except ImportError:
    TEMPORAL_EXCEPTION_TYPES = ()


def unwrap_temporal_failure(error: Exception) -> dict[str, Any]:
    error_chain: list[dict[str, str]] = []
    temporal_context: dict[str, Any] = {}
    current_error: Exception | None = error

    while current_error is not None:
        error_type = type(current_error).__name__
        error_message = str(current_error)

        error_chain.append({"type": error_type, "message": error_message})

        _extract_temporal_context(current_error, temporal_context)

        next_error = None

        if hasattr(current_error, "__cause__") and current_error.__cause__:
            next_error = current_error.__cause__
        elif hasattr(current_error, "cause") and current_error.cause:
            cause = current_error.cause
            if hasattr(cause, "message"):
                next_error = Exception(cause.message)
            else:
                next_error = cause if isinstance(cause, Exception) else None
        elif hasattr(current_error, "__context__") and current_error.__context__:
            next_error = current_error.__context__

        current_error = next_error

    root_error_type = error_chain[-1]["type"] if error_chain else "Unknown"
    root_error_message = error_chain[-1]["message"] if error_chain else str(error)

    retry_after_seconds = _extract_retry_after(root_error_message)

    return {
        "root_error_type": root_error_type,
        "root_error_message": root_error_message,
        "error_chain": error_chain,
        "temporal_context": temporal_context,
        "provider_retry_after_seconds": retry_after_seconds,
    }


def _extract_temporal_context(
    error: Exception, context: dict[str, Any]
) -> None:
    if hasattr(error, "activity_type"):
        context["activity_type"] = getattr(error, "activity_type", None)

    if hasattr(error, "activity_id"):
        context["activity_id"] = getattr(error, "activity_id", None)

    if hasattr(error, "scheduled_event_id"):
        context["scheduled_event_id"] = getattr(error, "scheduled_event_id", None)

    if hasattr(error, "started_event_id"):
        context["started_event_id"] = getattr(error, "started_event_id", None)

    if hasattr(error, "retry_state"):
        context["retry_state"] = getattr(error, "retry_state", None)

    if hasattr(error, "attempt"):
        context["attempt"] = getattr(error, "attempt", None)


def _extract_retry_after(message: str) -> float | None:
    patterns = [
        r"retry in (\d+\.?\d*)\s*s(?:ec(?:ond)?s?)?",
        r"retry after (\d+\.?\d*)\s*s(?:ec(?:ond)?s?)?",
        r"wait (\d+\.?\d*)\s*s(?:ec(?:ond)?s?)?",
        r"Please retry in (\d+\.?\d*)\s*s",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


__all__ = ["unwrap_temporal_failure"]

