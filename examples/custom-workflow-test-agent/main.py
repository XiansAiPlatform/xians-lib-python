"""
Custom Workflow Test Agent

Demonstrates:
- Built-in conversational workflow (Supervisor Workflow) using BuiltinWorkflow
- Custom Temporal workflow that takes start parameters (Input Parameters UI)
- Context Inspector workflow that validates XiansContext.CurrentAgent /
  CurrentWorkflow resolve correctly inside a Temporal activity

Run:
  cd examples/custom-workflow-test-agent
  pip install -r requirements.txt
  pip install -e ../..
  cp .env.example .env
  python main.py
"""

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv

# Add src to path for local development (matches other examples)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from xians.agents.core import XiansContext
from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration

from custom_input_workflow import AGENT_NAME, CustomInputWorkflow
from context_inspector_workflow import ContextInspectorWorkflow, inspect_context

logger = logging.getLogger(__name__)


async def main() -> None:
    load_dotenv()

    server_url = os.environ.get("XIANS_SERVER_URL")
    xians_api_key = os.environ.get("XIANS_API_KEY")

    if not server_url:
        raise RuntimeError("XIANS_SERVER_URL not found in environment variables")
    if not xians_api_key:
        raise RuntimeError("XIANS_API_KEY not found in environment variables")

    platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url=server_url,
            api_key=xians_api_key,
        )
    )

    agent = platform.agents.register(
        XiansAgentRegistration(
            name=AGENT_NAME,
            description="Agent to test built-in + custom workflows with input parameters",
            summary="Custom workflow test agent1",
            version="0.2.1",
            author="examples",
            is_template=True,
        )
    )

    # ── Upload local knowledge files (same pattern as web-search-agent) ──
    knowledge_files = [
        {
            "resource_path": "knowledge/system-instructions.md",
            "knowledge_name": "system-instructions",
            "knowledge_type": "markdown",
            "description": "System instructions for custom workflow test agent",
            "visible": False,
        },
        {
            "resource_path": "knowledge/agent-profile.json",
            "knowledge_name": "agent-profile",
            "knowledge_type": "json",
            "description": "Agent metadata and capabilities in JSON format",
            "visible": True,
        },
        {
            "resource_path": "knowledge/sample-notes.txt",
            "knowledge_name": "sample-notes",
            "knowledge_type": "text",
            "description": "Plain text local knowledge sample",
            "visible": True,
        },
        {
            "resource_path": "knowledge/workflow-config.xml",
            "knowledge_name": "workflow-config",
            "knowledge_type": "xml",
            "description": "Workflow configuration in XML format",
            "visible": True,
        },
        {
            "resource_path": "knowledge/settings.yaml",
            "knowledge_name": "settings-yaml",
            "knowledge_type": "yaml",
            "description": "YAML settings knowledge sample (.yaml)",
            "visible": True,
        },
        {
            "resource_path": "knowledge/settings-alt.yml",
            "knowledge_name": "settings-yml",
            "knowledge_type": "yaml",
            "description": "YAML settings knowledge sample (.yml)",
            "visible": True,
        },
    ]

    for kf in knowledge_files:
        try:
            success = await agent.knowledge.upload_from_file(**kf)
            if success:
                logger.info("Uploaded knowledge: %s", kf["knowledge_name"])
            else:
                logger.warning("Failed to upload knowledge: %s", kf["knowledge_name"])
        except Exception as ex:
            logger.warning(
                "Failed to upload knowledge '%s': %s. Agent will continue.",
                kf["knowledge_name"],
                ex,
            )

    # ── 1) Built-in conversational workflow ──
    builtin_wf = agent.define_builtin_workflow(name="Supervisor Workflow")

    async def handle_chat(context):
        """Echo handler that also demonstrates CurrentAgent / CurrentWorkflow access."""
        text = (context.message.text or "").strip()
        if not text:
            await context.reply_async("Send me a message and I'll echo it back.")
            return

        # Show CurrentAgent / CurrentWorkflow in chat reply for live verification
        try:
            current_agent = XiansContext.CurrentAgent
            current_wf = XiansContext.CurrentWorkflow
            header = (
                f"[Agent: {current_agent.name} | "
                f"Workflow: {current_wf.workflow_type}]\n\n"
            )
        except Exception:
            header = ""

        await context.reply_async(f"{header}Echo: {text}")

    builtin_wf.on_user_chat_message(handle_chat)

    # ── 2) Custom workflow: start-parameter driven ──
    custom_wf = agent.define_custom_workflow(CustomInputWorkflow)
    custom_wf.set_parameter_definitions(
        [
            {"name": "input", "type": "string", "optional": False},
            {"name": "times", "type": "integer", "optional": True},
            {"name": "uppercase", "type": "boolean", "optional": True},
        ]
    )

    # ── 3) Context Inspector workflow: validates CurrentAgent / CurrentWorkflow ──
    inspector_wf = agent.define_custom_workflow(ContextInspectorWorkflow)
    inspector_wf.add_activity(inspect_context)
    inspector_wf.set_parameter_definitions(
        [
            {"name": "query", "type": "string", "optional": True},
        ]
    )

    await agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())

