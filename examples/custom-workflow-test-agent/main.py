"""
Custom Workflow Test Agent

Demonstrates ALL messaging features:
- Built-in conversational workflow (Supervisor Workflow) with:
  - Chat handler with reasoning/tool progress, proactive messaging, history, handoff, skip_response
  - Data handler for structured data processing
  - File upload handler
  - Webhook handler with WebhookResponse factory methods
- Custom Temporal workflows:
  - Custom Input Workflow (start parameter driven)
  - Context Inspector Workflow (XiansContext validation)
  - Business Metrics Workflow (metrics API testing)
  - Messaging Test Workflow (proactive messaging from custom workflow activity)

Run:
  cd examples/custom-workflow-test-agent
  pip install -r requirements.txt
  pip install -e ../..
  cp .env.example .env
  python main.py
"""

import asyncio
import base64
import json
import logging
import os
import sys

from dotenv import load_dotenv

# Add src to path for local development (matches other examples)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from xians.agents.core import XiansContext
from xians.agents.messaging import UserMessageContext
from xians.agents.messaging.webhook_context import WebhookContext
from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration
from xians.temporal_workflows.v1.models import WebhookResponse

from custom_input_workflow import AGENT_NAME, CustomInputWorkflow
from context_inspector_workflow import ContextInspectorWorkflow, inspect_context
from business_metrics_workflow import BusinessMetricsWorkflow, report_business_metrics
from document_db_test_workflow import DocumentDBTestWorkflow, test_document_db
from messaging_test_workflow import MessagingTestWorkflow, test_proactive_messaging

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
            description="Agent to test built-in + custom workflows, all messaging features",
            summary="Custom workflow test agent with full messaging",
            version="0.3.1",
            author="examples",
            is_template=True,
        )
    )

    # ── Upload local knowledge files ──
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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1) Built-in conversational workflow — ALL message handlers
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    builtin_wf = agent.define_builtin_workflow(name="Supervisor Workflow")

    # ── CHAT HANDLER ──
    # Demonstrates: reply, reply_with_data, reasoning, tool_exec, proactive,
    #               history, task_id, skip_response, handoff, metrics
    async def handle_chat(context: UserMessageContext) -> None:
        text = (context.message.text or "").strip()
        if not text:
            await context.reply_async(
                "Send me a command:\n"
                "- `/echo <text>` — echo with progress\n"
                "- `/history` — get conversation history\n"
                "- `/taskid` — get last HITL task ID\n"
                "- `/proactive` — test proactive messaging\n"
                "- `/data` — reply with structured data\n"
                "- `/skip` — process silently (skip_response)\n"
                "- `/reasoning` — send reasoning progress\n"
                "- `/tool` — send tool execution progress\n"
                "- anything else — echo with context info"
            )
            return

        # Report message metric
        try:
            await context.metrics \
                .with_metric("messages", "received", 1, "count") \
                .report_async()
        except Exception as ex:
            logger.warning("Metrics report failed: %s", ex)

        # --- /echo — echo with reasoning/tool progress ---
        if text.lower().startswith("/echo"):
            payload = text[5:].strip() or "Hello!"
            await context.send_reasoning_async(f"Processing echo request: '{payload}'")
            await context.send_tool_exec_async("echo_processor(text=...)")
            await context.send_reasoning_async("Formatting response...")
            await context.reply_async(f"Echo: {payload}")
            return

        # --- /history — conversation history ---
        if text.lower() == "/history":
            history = await context.get_chat_history_async(page=1, page_size=10)
            if history:
                lines = [
                    f"- [{m.direction}] {(m.text or '')[:60]}"
                    for m in history
                ]
                await context.reply_async(
                    f"Last {len(history)} messages:\n" + "\n".join(lines)
                )
            else:
                await context.reply_async("No conversation history found.")
            return

        # --- /taskid — last HITL task ID ---
        if text.lower() == "/taskid":
            task_id = await context.get_last_task_id_async()
            await context.reply_async(
                f"Last task ID: {task_id}" if task_id else "No task ID found."
            )
            return

        # --- /proactive — test proactive messaging ---
        if text.lower() == "/proactive":
            await context.reply_async(
                "Testing proactive messaging via XiansContext.Messaging..."
            )

            # send_chat_async (auto-resolve participant from context)
            await XiansContext.Messaging.send_chat_async(
                text="Proactive chat message via XiansContext.Messaging!",
            )

            # send_data_async
            await XiansContext.Messaging.send_data_async(
                text="Proactive data message",
                data={
                    "test": "proactive_messaging",
                    "source": "chat_handler",
                    "status": "success",
                },
            )

            await context.reply_async(
                "Proactive messages sent! You should see 2 additional messages above."
            )
            return

        # --- /data — reply with structured data ---
        if text.lower() == "/data":
            await context.reply_async(
                "Here's a data reply with structured payload:",
                data={
                    "agent": XiansContext._resolve_agent_name(),
                    "workflow_type": XiansContext._resolve_workflow_type(),
                    "participant": context.message.participant_id,
                    "scope": context.message.scope,
                    "metadata": context.metadata,
                },
            )
            return

        # --- /skip — skip response (silent processing) ---
        if text.lower() == "/skip":
            context.skip_response = True
            logger.info("Received /skip — processing silently, no reply sent")
            await context.reply_async("This should NOT be sent")
            return

        # --- /reasoning — reasoning progress demo ---
        if text.lower() == "/reasoning":
            await context.send_reasoning_async("Step 1: Parsing user intent...")
            await context.send_reasoning_async("Step 2: Searching knowledge base...")
            await context.send_reasoning_async("Step 3: Synthesizing response...")
            await context.reply_async(
                "Reasoning demo complete! Three reasoning steps were streamed."
            )
            return

        # --- /tool — tool execution progress demo ---
        if text.lower() == "/tool":
            await context.send_tool_exec_async("search_documents(query='architecture')")
            await context.send_tool_exec_async("fetch_metadata(doc_id='DOC-001')")
            await context.send_tool_exec_async("format_response(template='summary')")
            await context.reply_async(
                "Tool execution demo complete! Three tool calls were streamed."
            )
            return

        # --- Default: echo with context info ---
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

    # ── DATA HANDLER ──
    # Demonstrates: receiving structured data, send_data_async response
    async def handle_data(context: UserMessageContext) -> None:
        data = context.message.data
        text = context.message.text or ""

        logger.info("Data message received: text=%s", text)

        await context.send_reasoning_async(
            f"Processing incoming data of type {type(data).__name__}..."
        )

        result = {
            "received_text": text,
            "received_data_type": type(data).__name__,
            "data_preview": str(data)[:200] if data else None,
            "participant_id": context.message.participant_id,
            "scope": context.message.scope,
            "processed": True,
        }

        await context.send_data_async(
            data=result,
            content="Data message processed",
        )

    builtin_wf.on_user_data_message(handle_data)

    # ── FILE UPLOAD HANDLER ──
    # Demonstrates: receiving files, extracting metadata, replying with results
    async def handle_file(context: UserMessageContext) -> None:
        raw_data = context.message.data
        file_name = context.message.text or "uploaded-file"

        if isinstance(raw_data, dict):
            base64_content = raw_data.get("content", "")
            file_name = raw_data.get("fileName", file_name)
            content_type = raw_data.get("contentType", "unknown")
            file_size = raw_data.get("fileSize")
        elif isinstance(raw_data, str):
            base64_content = raw_data
            content_type = "unknown"
            file_size = None
        else:
            base64_content = str(raw_data) if raw_data else ""
            content_type = "unknown"
            file_size = None

        if not base64_content:
            await context.reply_async("No file data received.")
            return

        try:
            file_bytes = base64.b64decode(base64_content)
            size_kb = len(file_bytes) / 1024

            await context.send_reasoning_async(
                f"Processing file: {file_name} ({size_kb:.1f} KB)"
            )

            await context.reply_async(
                f"File processed!\n"
                f"- Name: {file_name}\n"
                f"- Size: {size_kb:.1f} KB ({len(file_bytes)} bytes)\n"
                f"- Content type: {content_type}",
                data={
                    "fileName": file_name,
                    "sizeBytes": len(file_bytes),
                    "contentType": content_type,
                    "status": "processed",
                },
            )
        except Exception as e:
            await context.reply_async(f"Error processing file: {e}")

    builtin_wf.on_file_upload(handle_file)

    # ── WEBHOOK HANDLER ──
    # Demonstrates: WebhookContext, respond, respond_with, factory methods
    async def handle_webhook(context: WebhookContext) -> None:
        payload = context.webhook.payload
        scope = context.webhook.scope

        logger.info("Webhook received: scope=%s", scope)

        if isinstance(payload, dict):
            action = payload.get("action", "")

            if action == "ping":
                context.respond({"status": "pong", "scope": scope})
                return

            if action == "status":
                context.respond({
                    "agent": AGENT_NAME,
                    "status": "running",
                    "scope": scope,
                })
                return

            if action == "error_test":
                context.respond_with(WebhookResponse.bad_request("Test error response"))
                return

            if action == "not_found_test":
                context.respond_with(WebhookResponse.not_found("Resource not found"))
                return

        context.respond({
            "status": "received",
            "scope": scope,
            "payload_type": type(payload).__name__,
        })

    builtin_wf.on_webhook(handle_webhook)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2) Custom workflow: start-parameter driven
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    custom_wf = agent.define_custom_workflow(CustomInputWorkflow)
    custom_wf.set_parameter_definitions(
        [
            {"name": "input", "type": "string", "optional": False},
            {"name": "times", "type": "integer", "optional": True},
            {"name": "uppercase", "type": "boolean", "optional": True},
        ]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3) Context Inspector workflow
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    inspector_wf = agent.define_custom_workflow(ContextInspectorWorkflow)
    inspector_wf.add_activity(inspect_context)
    inspector_wf.set_parameter_definitions(
        [
            {"name": "query", "type": "string", "optional": True},
        ]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4) Business Metrics workflow
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    metrics_wf = agent.define_custom_workflow(BusinessMetricsWorkflow)
    metrics_wf.add_activity(report_business_metrics)
    metrics_wf.set_parameter_definitions(
        [
            {
                "name": "scenario",
                "type": "string",
                "optional": True,
            },
        ]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5) Document DB Test workflow — full CRUD + query + TTL + upsert
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    docdb_wf = agent.define_custom_workflow(DocumentDBTestWorkflow)
    docdb_wf.add_activity(test_document_db)
    docdb_wf.set_parameter_definitions(
        [
            {"name": "scenario", "type": "string", "optional": True},
        ]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6) Messaging Test workflow — proactive messaging from a custom workflow
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    messaging_wf = agent.define_custom_workflow(MessagingTestWorkflow)
    messaging_wf.add_activity(test_proactive_messaging)
    messaging_wf.set_parameter_definitions(
        [
            {"name": "participant_id", "type": "string", "optional": False},
            {"name": "scenario", "type": "string", "optional": True},
        ]
    )

    await agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())

