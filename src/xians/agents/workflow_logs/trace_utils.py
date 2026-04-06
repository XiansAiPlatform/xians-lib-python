"""Shared OpenTelemetry trace-context helper."""

from __future__ import annotations


def current_trace_context() -> tuple[str | None, str | None]:
    """Extract OpenTelemetry trace/span IDs when instrumentation is active."""
    try:
        from opentelemetry import trace as otel_trace  # type: ignore

        span = otel_trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is None or not getattr(ctx, "is_valid", False):
            return None, None
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        return None, None
