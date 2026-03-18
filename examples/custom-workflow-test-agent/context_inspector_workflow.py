"""Custom Temporal workflow that introspects XiansContext.CurrentAgent / CurrentWorkflow.

Takes a user query, resolves the current agent and workflow from XiansContext,
and returns a structured report with all available metadata. This validates
that the Python SDK's CurrentAgent / CurrentWorkflow properties resolve
correctly inside a Temporal activity — just like C# XiansContext.CurrentAgent
and XiansContext.CurrentWorkflow.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow

from custom_input_workflow import AGENT_NAME


@activity.defn(name="InspectContext")
async def inspect_context(query: str) -> str:
    """Activity that reads XiansContext.CurrentAgent / CurrentWorkflow.

    Because this runs inside a Temporal activity, the SDK has already populated
    the async-local context (workflow ID, workflow type, agent name, etc.)
    via MessageActivities — so the properties resolve without any manual setup.
    """
    # Import lazily inside the activity. The workflow module is validated inside
    # Temporal's sandbox, which restricts some transitive imports.
    from xians.agents.core import XiansContext

    report: dict[str, Any] = {
        "query": query,
        "context": {},
        "current_agent": None,
        "current_workflow": None,
        "all_registered_agents": [],
        "all_registered_workflows": [],
    }

    report["context"] = {
        "tenant_id": XiansContext.get_tenant_id(),
        "participant_id": XiansContext.get_participant_id(),
        "request_id": XiansContext.get_request_id(),
        "workflow_id": XiansContext.get_workflow_id(),
        "id_postfix": XiansContext.get_id_postfix(),
    }

    try:
        agent = XiansContext.CurrentAgent
        report["current_agent"] = {
            "name": agent.name,
            "system_scoped": agent.system_scoped,
            "tenant_id": getattr(agent, "_tenant_id", None),
            "workflows_count": len(getattr(agent, "_workflows", [])),
        }
    except (RuntimeError, KeyError) as e:
        report["current_agent"] = {"error": str(e)}

    try:
        wf = XiansContext.CurrentWorkflow
        report["current_workflow"] = {
            "workflow_type": wf.workflow_type,
            "workflow_name": wf.workflow_name,
            "agent_name": wf.agent_name,
            "workers": wf.workers,
            "system_scoped": wf.system_scoped,
            "tenant_id": wf.tenant_id,
            "max_history_length": wf.max_history_length,
        }
    except (RuntimeError, KeyError) as e:
        report["current_workflow"] = {"error": str(e)}

    for a in XiansContext.get_all_agents():
        report["all_registered_agents"].append(getattr(a, "name", str(a)))

    for w in XiansContext.get_all_workflows():
        report["all_registered_workflows"].append(getattr(w, "workflow_type", str(w)))

    return json.dumps(report, indent=2, default=str)


@workflow.defn(name=f"{AGENT_NAME}:Context Inspector Workflow")
class ContextInspectorWorkflow:
    """Custom workflow that runs InspectContext activity and returns the report.

    Start this from the UI with a single string parameter. It will inspect
    the XiansContext and return a JSON report proving CurrentAgent and
    CurrentWorkflow resolve correctly.
    """

    @workflow.run
    async def run(self, query: str = "inspect") -> str:
        return await workflow.execute_activity(
            inspect_context,
            query,
            start_to_close_timeout=timedelta(seconds=30),
        )
