"""
Custom Workflow Test Agent

Demonstrates:
- Built-in conversational workflow (Supervisor Workflow) using BuiltinWorkflow
- Custom Temporal workflow that takes start parameters (Input Parameters UI)

Run:
  cd examples/custom-workflow-test-agent
  pip install -r requirements.txt
  pip install -e ../..
  cp .env.example .env
  python main.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add src to path for local development (matches other examples)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration

from custom_input_workflow import AGENT_NAME, CustomInputWorkflow


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
            summary="Custom workflow test agent",
            version="0.1.0",
            author="examples",
            is_template=True,
        )
    )

    # Built-in conversational workflow
    builtin_wf = agent.define_builtin_workflow(name="Supervisor Workflow")

    async def handle_chat(context):
        text = (context.message.text or "").strip()
        if not text:
            await context.reply_async("Send me a chat message and I'll echo it back.")
            return
        await context.reply_async(f"Echo (builtin): {text}")

    builtin_wf.on_user_chat_message(handle_chat)

    # Custom workflow: start-parameter driven
    custom_wf = agent.define_custom_workflow(CustomInputWorkflow)

    # Explicit parameterDefinitions so the UI shows friendly types (C# parity-like).
    # If you omit this, the SDK will best-effort infer from run(...) signature.
    custom_wf.set_parameter_definitions(
        [
            {"name": "input", "type": "string", "optional": False},
            {"name": "times", "type": "integer", "optional": True},
            {"name": "uppercase", "type": "boolean", "optional": True},
        ]
    )

    await agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())

