"""
Web Search Agent — Python equivalent of the C# ExampleAgents pattern.

This agent uses LangChain + DuckDuckGo web search to answer user queries with
real-time information from the web. It demonstrates all messaging features:

    - Chat message handler with reasoning/tool progress streaming
    - Data message handler for structured queries
    - File upload handler for document processing
    - Webhook handler for external integrations
    - Proactive messaging from within handlers

Prerequisites:
    pip install langchain-openai langchain-community duckduckgo-search langgraph

Environment variables (.env):
    OPENAI_API_KEY=sk-...
    XIANS_SERVER_URL=https://api.agentri.ai
    XIANS_API_KEY=<base64 certificate>
"""

import asyncio
import base64
import json
import logging
import os
import sys

from dotenv import load_dotenv

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from xians.agents.core import XiansContext
from xians.agents.messaging import UserMessageContext
from xians.agents.messaging.webhook_context import WebhookContext
from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration
from xians.temporal_workflows.v1.models import WebhookResponse

from web_search_sub_agent import WebSearchSubAgent

logger = logging.getLogger(__name__)


async def main() -> None:
    load_dotenv()

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    server_url = os.environ.get("XIANS_SERVER_URL")
    xians_api_key = os.environ.get("XIANS_API_KEY")
    console_log_level = os.environ.get("CONSOLE_LOG_LEVEL", "DEBUG")
    server_log_level = os.environ.get("SERVER_LOG_LEVEL", "Information")

    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment variables")
    if not server_url:
        raise RuntimeError("XIANS_SERVER_URL not found in environment variables")
    if not xians_api_key:
        raise RuntimeError("XIANS_API_KEY not found in environment variables")

    # ── Step 1: Initialize platform ──
    xians_platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url=server_url,
            api_key=xians_api_key,
            console_log_level=console_log_level,
            server_log_level=server_log_level,
        )
    )

    # ── Step 2: Register agent ──
    xians_agent = xians_platform.agents.register(
        XiansAgentRegistration(
            name="Web Search Agent7",
            description=(
                "AI-powered web search assistant that finds and summarizes "
                "real-time information from the internet using Tavily search."
            ),
            summary="Web search agent with LangChain tools",
            version="1.0.5",
            author="99x",
            is_template=True,
        )
    )

    # ── Step 3: Upload knowledge files ──
    knowledge_files = [
        {
            "resource_path": "knowledge/system-instructions.md",
            "knowledge_name": "system-instructions",
            "knowledge_type": "markdown",
            "description": "System instructions for the web search agent",
            "visible": False,
        },
    ]

    for kf in knowledge_files:
        try:
            success = await xians_agent.knowledge.upload_from_file(**kf)
            if success:
                logger.info("Uploaded knowledge: %s", kf["knowledge_name"])
            else:
                logger.warning("Failed to upload knowledge: %s", kf["knowledge_name"])
        except Exception as ex:
            logger.warning(
                "Failed to upload knowledge '%s': %s. Agent will continue with defaults.",
                kf["knowledge_name"],
                ex,
            )

    # ── Step 4: Define workflow ──
    conversational_workflow = xians_agent.define_builtin_workflow(
        name="Supervisor Workflow"
    )

    # ── Step 5: Create sub-agent (the LangChain agent with tools) ──
    search_sub_agent = WebSearchSubAgent(
        openai_api_key=openai_api_key,
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CHAT HANDLER — Demonstrates:
    #   - send_reasoning_async / send_tool_exec_async (progress messages)
    #   - reply_async with data
    #   - Proactive messaging via XiansContext.Messaging
    #   - Conversation history retrieval
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def handle_chat(context: UserMessageContext) -> None:
        text = (context.message.text or "").strip()

        # --- Command: /history — get conversation history ---
        if text.lower() == "/history":
            history = await context.get_chat_history_async(page=1, page_size=10)
            if history:
                lines = [f"- [{m.direction}] {m.text[:80]}" for m in history]
                await context.reply_async(
                    f"Last {len(history)} messages:\n" + "\n".join(lines)
                )
            else:
                await context.reply_async("No conversation history found.")
            return

        # --- Command: /proactive — test proactive messaging ---
        if text.lower() == "/proactive":
            await context.reply_async(
                "Testing proactive messaging... sending a follow-up in 2 seconds."
            )
            await XiansContext.Messaging.send_chat_async(
                text="This is a proactive message sent via XiansContext.Messaging!",
            )
            await XiansContext.Messaging.send_data_async(
                text="Proactive data message",
                data={"type": "proactive_test", "status": "success"},
            )
            return

        # --- Command: /taskid — get last HITL task ID ---
        if text.lower() == "/taskid":
            task_id = await context.get_last_task_id_async()
            await context.reply_async(
                f"Last task ID: {task_id}" if task_id else "No task ID found."
            )
            return

        # --- Default: web search with progress streaming ---
        response = await search_sub_agent.run_async(context)
        await context.reply_async(response)

    conversational_workflow.on_user_chat_message(handle_chat)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # DATA HANDLER — Demonstrates:
    #   - Receiving structured data from clients
    #   - send_data_async for structured response
    #   - Processing JSON payloads
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def handle_data(context: UserMessageContext) -> None:
        data = context.message.data
        text = context.message.text or ""

        logger.info("Data message received: text=%s data_type=%s", text, type(data).__name__)

        result = {
            "received_text": text,
            "received_data_type": type(data).__name__,
            "received_data": data,
            "processed": True,
            "message": "Data received and processed successfully!",
        }

        await context.send_data_async(
            data=result,
            content="Data processed successfully",
        )

    conversational_workflow.on_user_data_message(handle_data)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE UPLOAD HANDLER — Demonstrates:
    #   - Receiving base64-encoded files
    #   - Extracting metadata (fileName, contentType)
    #   - Replying with processing results
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def handle_file(context: UserMessageContext) -> None:
        raw_data = context.message.data
        file_name = context.message.text or "uploaded-file"

        if isinstance(raw_data, dict):
            base64_content = raw_data.get("content", "")
            file_name = raw_data.get("fileName", file_name)
            content_type = raw_data.get("contentType", "unknown")
        elif isinstance(raw_data, str):
            base64_content = raw_data
            content_type = "unknown"
        else:
            base64_content = str(raw_data) if raw_data else ""
            content_type = "unknown"

        if not base64_content:
            await context.reply_async("No file data received. Please send a base64-encoded file.")
            return

        try:
            file_bytes = base64.b64decode(base64_content)
            size_kb = len(file_bytes) / 1024

            await context.send_reasoning_async(
                f"Processing file: {file_name} ({size_kb:.1f} KB, type: {content_type})"
            )

            await context.reply_async(
                f"File received and processed!\n"
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
            await context.reply_async(
                f"Error processing file: {e}. Please ensure the file is base64 encoded."
            )

    conversational_workflow.on_file_upload(handle_file)

    def _respond_webhook_json(webhook_context: WebhookContext, data: dict) -> None:
        """JSON webhook reply with empty headers object (not null) for C# deserialization."""
        webhook_context.respond_with(
            WebhookResponse(
                status_code=200,
                content=json.dumps(data, default=str),
                content_type="application/json",
                headers={},
            )
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # WEBHOOK HANDLER — Demonstrates:
    #   - Receiving webhook payloads
    #   - Responding with WebhookResponse (OK, error, custom)
    #   - WebhookResponse factory methods
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def handle_webhook(context: WebhookContext) -> None:
        payload = context.webhook.payload
        scope = context.webhook.scope
        name = context.webhook.name

        logger.info(
            "Webhook received: scope=%s name=%s payload_type=%s",
            scope, name, type(payload).__name__,
        )

        if isinstance(payload, dict) and payload.get("action") == "ping":
            _respond_webhook_json(context, {"status": "pong", "scope": scope})
            return

        if isinstance(payload, dict) and payload.get("action") == "error_test":
            err = WebhookResponse.bad_request("Intentional test error")
            err.headers = {}
            context.respond_with(err)
            return

        _respond_webhook_json(context, {
            "status": "received",
            "scope": scope,
            "payload_type": type(payload).__name__,
            "message": "Webhook processed successfully",
        })

    conversational_workflow.on_webhook(handle_webhook)

    # ── Step 7: Start ──
    await xians_agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())
