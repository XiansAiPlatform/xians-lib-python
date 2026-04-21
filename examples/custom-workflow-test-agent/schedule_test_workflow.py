"""Custom workflow that exercises the scheduling API end-to-end.

Run it from the UI with an optional ``scenario`` parameter to validate:

- ``create_if_not_exists_async`` (idempotent creation)
- ``get_async`` / ``exists_async``
- ``pause_async`` / ``unpause_async``
- ``trigger_async``
- ``delete_async``

The workflow target of the created schedule is :class:`ScheduleTargetWorkflow`
below, a trivial workflow that records every invocation so you can observe
schedule-triggered runs in Temporal.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow

from custom_input_workflow import AGENT_NAME


# ---------------------------------------------------------------------------
# Target workflow invoked by the schedule
# ---------------------------------------------------------------------------

@workflow.defn(name=f"{AGENT_NAME}:Schedule Target Workflow")
class ScheduleTargetWorkflow:
    """Trivial workflow used as the scheduled action. Each run logs its input
    and returns a summary string, so you can confirm schedule executions in
    Temporal UI.
    """

    @workflow.run
    async def run(self, report_type: str = "summary") -> str:
        workflow.logger.info(
            "ScheduleTargetWorkflow invoked with report_type=%s", report_type
        )
        return f"scheduled-run:{report_type}"


# ---------------------------------------------------------------------------
# Activity that exercises the schedule lifecycle
# ---------------------------------------------------------------------------

SCHEDULE_NAME = "Schedule Target Workflow-schedule"


@activity.defn(name="TestScheduling")
async def test_scheduling(scenario: str = "full") -> str:
    """Run the schedule lifecycle from inside an activity.

    Running as an activity means ``XiansContext.CurrentAgent.schedules`` hits
    the Temporal client directly (not via activities-from-workflow), which
    keeps this example simple and the output easy to reason about.
    """
    from xians.agents.core import XiansContext

    agent = XiansContext.CurrentAgent
    results: dict[str, Any] = {"scenario": scenario, "steps": []}

    def log_step(name: str, data: Any) -> None:
        results["steps"].append({"step": name, "data": data})

    try:
        # ── 1. Clean slate ──
        try:
            await agent.schedules.delete_async(SCHEDULE_NAME)
            log_step("cleanup_previous", {"deleted": True})
        except Exception:
            log_step("cleanup_previous", {"deleted": False})

        # ── 2. Create idempotently with an interval schedule ──
        schedule = await (
            agent.schedules
            .create(SCHEDULE_NAME, ScheduleTargetWorkflow)
            .every_seconds(30)
            .with_input("daily")
            .with_memo({"owner": "schedule-test", "env": "example"})
            .skip_if_running()
            .create_if_not_exists_async()
        )
        log_step("create_if_not_exists", {"id": schedule.id})

        # ── 3. Idempotent second call returns the same schedule ──
        again = await (
            agent.schedules
            .create(SCHEDULE_NAME, ScheduleTargetWorkflow)
            .every_seconds(30)
            .with_input("daily")
            .create_if_not_exists_async()
        )
        log_step("create_if_not_exists_again", {
            "id": again.id,
            "same": again.id == schedule.id,
        })

        # ── 4. Exists ──
        exists = await agent.schedules.exists_async(SCHEDULE_NAME)
        log_step("exists", {"exists": exists})

        # ── 5. Describe via get_async ──
        fetched = await agent.schedules.get_async(SCHEDULE_NAME)
        description = await fetched.describe_async()
        log_step("describe", {
            "id": fetched.id,
            "next_actions": [str(t) for t in (description.info.next_action_times or [])[:3]],
        })

        # ── 6. Pause / Unpause ──
        await agent.schedules.pause_async(SCHEDULE_NAME, note="test cleanup")
        log_step("pause", {"ok": True})
        await agent.schedules.unpause_async(SCHEDULE_NAME, note="back online")
        log_step("unpause", {"ok": True})

        # ── 7. Trigger an immediate run ──
        await agent.schedules.trigger_async(SCHEDULE_NAME)
        log_step("trigger", {"ok": True})

        # # ── 8. Delete ──
        # await agent.schedules.delete_async(SCHEDULE_NAME)
        # log_step("delete", {"ok": True})

        exists_after = await agent.schedules.exists_async(SCHEDULE_NAME)
        log_step("exists_after_delete", {"exists": exists_after})

        results["success"] = True

    except Exception as ex:
        results["success"] = False
        results["error"] = str(ex)
        activity.logger.error("Schedule test failed: %s", ex, exc_info=True)

    return json.dumps(results, indent=2, default=str)


# ---------------------------------------------------------------------------
# Driver workflow
# ---------------------------------------------------------------------------

@workflow.defn(name=f"{AGENT_NAME}:Schedule Test Workflow")
class ScheduleTestWorkflow:
    """Driver workflow that invokes the schedule-lifecycle activity."""

    @workflow.run
    async def run(self, scenario: str = "full") -> str:
        return await workflow.execute_activity(
            test_scheduling,
            scenario,
            start_to_close_timeout=timedelta(minutes=2),
        )
