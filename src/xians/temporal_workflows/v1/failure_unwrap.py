"""Failure unwrapping utility for Temporal exceptions.

This module provides deterministic error unwrapping for Temporal exceptions,
extracting root causes and structured diagnostic information.
"""

import re
from typing import Any

# Import Temporal exception types with graceful fallback
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
    # Fallback if some types aren't available
    TEMPORAL_EXCEPTION_TYPES = ()


def unwrap_temporal_failure(error: Exception) -> dict[str, Any]:
    """
    Unwrap Temporal exceptions to extract root cause and diagnostic details.

    This function is deterministic and safe to run inside workflow code.
    It walks the exception chain and extracts structured information.

    Args:
        error: The exception to unwrap.

    Returns:
        A dictionary containing:
            - root_error_type: Type name of the root cause exception
            - root_error_message: Message from the root cause
            - error_chain: List of {type, message} dicts in order from outer to root
            - temporal_context: Activity/workflow metadata when available
            - provider_retry_after_seconds: Parsed retry-after duration if present

    Example:
        >>> error_details = unwrap_temporal_failure(activity_error)
        >>> error_details["root_error_message"]
        "429 You exceeded your current quota. Please retry in 32.439s"
        >>> error_details["provider_retry_after_seconds"]
        32.439
    """
    error_chain: list[dict[str, str]] = []
    temporal_context: dict[str, Any] = {}
    current_error: Exception | None = error

    # Walk the exception chain
    while current_error is not None:
        error_type = type(current_error).__name__
        error_message = str(current_error)

        error_chain.append({"type": error_type, "message": error_message})

        # Extract Temporal-specific context
        _extract_temporal_context(current_error, temporal_context)

        # Move to next in chain
        next_error = None

        # Try standard __cause__
        if hasattr(current_error, "__cause__") and current_error.__cause__:
            next_error = current_error.__cause__
        # Try Temporal's cause attribute
        elif hasattr(current_error, "cause") and current_error.cause:
            cause = current_error.cause
            # Temporal's cause might be a Failure object; convert to exception
            if hasattr(cause, "message"):
                # Create a synthetic exception from Failure
                next_error = Exception(cause.message)
            else:
                next_error = cause if isinstance(cause, Exception) else None
        # Try underlying __context__
        elif hasattr(current_error, "__context__") and current_error.__context__:
            next_error = current_error.__context__

        current_error = next_error

    # Root cause is the last in the chain
    root_error_type = error_chain[-1]["type"] if error_chain else "Unknown"
    root_error_message = error_chain[-1]["message"] if error_chain else str(error)

    # Parse retry-after from message patterns
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
    """
    Extract Temporal-specific metadata from an exception.

    Mutates the context dict in-place.

    Args:
        error: The exception to extract from.
        context: Dictionary to populate with metadata.
    """
    # ActivityError has activity_type, activity_id, etc.
    if hasattr(error, "activity_type"):
        context["activity_type"] = getattr(error, "activity_type", None)

    if hasattr(error, "activity_id"):
        context["activity_id"] = getattr(error, "activity_id", None)

    if hasattr(error, "scheduled_event_id"):
        context["scheduled_event_id"] = getattr(error, "scheduled_event_id", None)

    if hasattr(error, "started_event_id"):
        context["started_event_id"] = getattr(error, "started_event_id", None)

    # Retry state
    if hasattr(error, "retry_state"):
        context["retry_state"] = getattr(error, "retry_state", None)

    # Attempt count
    if hasattr(error, "attempt"):
        context["attempt"] = getattr(error, "attempt", None)


def _extract_retry_after(message: str) -> float | None:
    """
    Extract retry-after duration from error messages.

    Looks for patterns like:
        - "Please retry in 32.439s"
        - "retry after 15 seconds"
        - "wait 30s before retrying"

    Args:
        message: The error message to parse.

    Returns:
        Retry duration in seconds, or None if not found.
    """
    # Pattern: "retry in X.Ys" or "retry in Xs"
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

