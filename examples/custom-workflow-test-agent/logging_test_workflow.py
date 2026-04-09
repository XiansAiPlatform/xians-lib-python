"""Custom workflow that validates Xians logging end-to-end.

Demonstrates:
- XiansLogger in activities (see ``logging_test_activities.py``)
- Standard Python logger usage
- Context-aware metadata extraction
- LoggingServices queue statistics

The activity lives in a separate module so imports like ``httpx`` are not loaded
inside Temporal's workflow sandbox during worker validation.

Start from the UI with parameters:
  scenario: "basic" | "error" | "all" (optional, default "all")
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

from custom_input_workflow import AGENT_NAME

# Activity name must match @activity.defn in logging_test_activities.
_RUN_LOGGING_TEST = "RunLoggingTest"


@workflow.defn(name=f"{AGENT_NAME}:Logging Test Workflow")
class LoggingTestWorkflow:
    """Custom workflow for validating logging behavior."""

    @workflow.run
    async def run(self, scenario: str = "all") -> str:
        return await workflow.execute_activity(
            _RUN_LOGGING_TEST,
            args=[scenario],
            start_to_close_timeout=timedelta(minutes=5),
        )
