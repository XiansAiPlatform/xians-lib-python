"""Custom workflow that tests proactive messaging from a Temporal activity.

Demonstrates:
- UserMessaging.send_chat_async (direct, from activity context)
- UserMessaging.send_data_async
- UserMessaging.send_chat_as_workflow_async (impersonate a builtin workflow)
- UserMessaging.send_reasoning_async
- UserMessaging.send_tool_call_async
- UserMessaging.get_last_task_id_async
- XiansContext.Messaging facade (auto participant resolution)

Start from the UI with parameters:
  participant_id: "user@example.com" (required — who to send messages to)
  scenario: "chat" | "data" | "as_workflow" | "progress" | "all" (optional, default "all")
"""

from __future__ import annotations

import json
from datetime import timedelta

from temporalio import activity, workflow

from custom_input_workflow import AGENT_NAME


@activity.defn(name="TestProactiveMessaging")
async def test_proactive_messaging(participant_id: str, scenario: str) -> str:
    """Activity that sends proactive messages using UserMessaging and XiansContext.Messaging.

    Runs inside a Temporal activity where XiansContext is populated, so both
    UserMessaging (low-level) and XiansContext.Messaging (facade) work.
    """
    from xians.agents.core import XiansContext
    from xians.agents.messaging import UserMessaging

    results: list[str] = []
    scenario = (scenario or "all").lower()

    # --- Scenario: chat — Send proactive chat messages ---
    if scenario in ("chat", "all"):
        try:
            await UserMessaging.send_chat_async(
                participant_id=participant_id,
                text="Hello! This is a proactive chat message from UserMessaging.",
            )
            results.append("send_chat_async: OK")
        except Exception as e:
            results.append(f"send_chat_async: ERROR - {e}")

        try:
            await UserMessaging.send_chat_async(
                participant_id=participant_id,
                text="Chat with scope and hint",
                scope="test-notifications",
                hint="proactive-test",
            )
            results.append("send_chat_async (with scope/hint): OK")
        except Exception as e:
            results.append(f"send_chat_async (with scope/hint): ERROR - {e}")

    # --- Scenario: data — Send proactive data messages ---
    if scenario in ("data", "all"):
        try:
            await UserMessaging.send_data_async(
                participant_id=participant_id,
                text="Proactive data message",
                data={
                    "type": "test_notification",
                    "items": [1, 2, 3],
                    "metadata": {"source": "messaging_test_workflow"},
                },
            )
            results.append("send_data_async: OK")
        except Exception as e:
            results.append(f"send_data_async: ERROR - {e}")

    # --- Scenario: as_workflow — Send messages impersonating a builtin workflow ---
    if scenario in ("as_workflow", "all"):
        try:
            await UserMessaging.send_chat_as_workflow_async(
                builtin_workflow_name="Supervisor Workflow",
                participant_id=participant_id,
                text="This message appears to come from the Supervisor Workflow!",
            )
            results.append("send_chat_as_workflow_async: OK")
        except Exception as e:
            results.append(f"send_chat_as_workflow_async: ERROR - {e}")

        try:
            await UserMessaging.send_data_as_workflow_async(
                builtin_workflow_name="Supervisor Workflow",
                participant_id=participant_id,
                text="Data as Supervisor",
                data={"impersonated": True, "workflow": "Supervisor Workflow"},
            )
            results.append("send_data_as_workflow_async: OK")
        except Exception as e:
            results.append(f"send_data_as_workflow_async: ERROR - {e}")

    # --- Scenario: progress — Send reasoning and tool call messages ---
    if scenario in ("progress", "all"):
        try:
            await UserMessaging.send_reasoning_async(
                builtin_workflow_name="Supervisor Workflow",
                participant_id=participant_id,
                text="Analyzing the request parameters...",
            )
            results.append("send_reasoning_async: OK")
        except Exception as e:
            results.append(f"send_reasoning_async: ERROR - {e}")

        try:
            await UserMessaging.send_tool_call_async(
                builtin_workflow_name="Supervisor Workflow",
                participant_id=participant_id,
                text="execute_query(table='orders', filter='status=pending')",
            )
            results.append("send_tool_call_async: OK")
        except Exception as e:
            results.append(f"send_tool_call_async: ERROR - {e}")

    # --- Scenario: facade — Test XiansContext.Messaging facade ---
    if scenario in ("facade", "all"):
        XiansContext.set_participant_id(participant_id)

        try:
            await XiansContext.Messaging.send_chat_async(
                text="Message via XiansContext.Messaging facade (auto-participant)!",
            )
            results.append("XiansContext.Messaging.send_chat_async: OK")
        except Exception as e:
            results.append(f"XiansContext.Messaging.send_chat_async: ERROR - {e}")

        try:
            await XiansContext.Messaging.send_data_async(
                text="Data via facade",
                data={"facade": True, "auto_participant": True},
            )
            results.append("XiansContext.Messaging.send_data_async: OK")
        except Exception as e:
            results.append(f"XiansContext.Messaging.send_data_async: ERROR - {e}")

        try:
            await XiansContext.Messaging.send_chat_as_supervisor_async(
                text="Supervisor message via facade!",
            )
            results.append("XiansContext.Messaging.send_chat_as_supervisor_async: OK")
        except Exception as e:
            results.append(f"XiansContext.Messaging.send_chat_as_supervisor_async: ERROR - {e}")

    # --- Scenario: task_id — Test get_last_task_id ---
    if scenario in ("task_id", "all"):
        try:
            task_id = await UserMessaging.get_last_task_id_async(
                participant_id=participant_id,
            )
            results.append(f"get_last_task_id_async: OK (task_id={task_id})")
        except Exception as e:
            results.append(f"get_last_task_id_async: ERROR - {e}")

    report = {
        "scenario": scenario,
        "participant_id": participant_id,
        "results": results,
        "total_tests": len(results),
        "passed": sum(1 for r in results if "OK" in r),
        "failed": sum(1 for r in results if "ERROR" in r),
    }

    return json.dumps(report, indent=2)


@workflow.defn(name=f"{AGENT_NAME}:Messaging Test Workflow")
class MessagingTestWorkflow:
    """Custom workflow that tests all proactive messaging APIs.

    Start from the UI with parameters:
      participant_id: "user@example.com" (who to send test messages to)
      scenario: "chat" | "data" | "as_workflow" | "progress" | "facade" | "task_id" | "all"

    The workflow runs the test activity and returns a JSON report with results.
    Messages are sent to the specified participant during execution.
    """

    @workflow.run
    async def run(self, participant_id: str, scenario: str = "all") -> str:
        return await workflow.execute_activity(
            test_proactive_messaging,
            args=[participant_id, scenario],
            start_to_close_timeout=timedelta(minutes=5),
        )
