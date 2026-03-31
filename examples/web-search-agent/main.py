"""
Web Search Agent — Python equivalent of the C# ExampleAgents pattern.

This agent uses LangChain + DuckDuckGo web search to answer user queries with
real-time information from the web. It is registered on the Xians platform
using the same pattern as the C# secrets-agent/healthcare-agent examples:

    XiansPlatform.initialize(options)
    -> agents.register(registration)
    -> define_builtin_workflow("Conversational")
    -> on_user_chat_message(handler)
    -> run_all_async()

System instructions are loaded from Knowledge at runtime. At startup, the
agent uploads local knowledge files to the platform (matching the C# pattern
of UploadEmbeddedResourceAsync). The knowledge file lives at:
    knowledge/system-instructions.md

Prerequisites:
    pip install langchain-openai langchain-community duckduckgo-search langgraph

Environment variables (.env):
    OPENAI_API_KEY=sk-...
    XIANS_SERVER_URL=https://api.agentri.ai
    XIANS_API_KEY=<base64 certificate>
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration

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

    # ── Step 1: Initialize platform (matches C# XiansPlatform.InitializeAsync) ──
    xians_platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url=server_url,
            api_key=xians_api_key,
            console_log_level=console_log_level,
            server_log_level=server_log_level,
        )
    )

    # ── Step 2: Register agent (matches C# xiansPlatform.Agents.Register) ──
    xians_agent = xians_platform.agents.register(
        XiansAgentRegistration(
            name="Web Search Agent9",
            description=(
                "AI-powered web search assistant that finds and summarizes "
                "real-time information from the internet using Tavily search."
            ),
            summary="Web search agent with LangChain tools",
            version="1.0.4",
            author="99x",
            is_template=True,
        )
    )

    # ── Step 3: Upload knowledge files (matches C# UploadEmbeddedResourceAsync) ──
    #
    # This mirrors the C# pattern where knowledge files are uploaded to the
    # platform at startup. At runtime, the agent fetches them with get_async().
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

    # ── Step 4: Define workflow (matches C# DefineBuiltIn) ──
    conversational_workflow = xians_agent.define_builtin_workflow(
        name="Supervisor Workflow"
    )

    # ── Step 5: Create sub-agent (the LangChain agent with tools) ──
    search_sub_agent = WebSearchSubAgent(
        openai_api_key=openai_api_key,
    )

    # ── Step 6: Wire up handler (matches C# OnUserChatMessage) ──
    async def handle_chat(context):
        response = await search_sub_agent.run_async(context)
        await context.reply_async(response)

    conversational_workflow.on_user_chat_message(handle_chat)

    # ── Step 7: Start (matches C# RunAllAsync) ──
    await xians_agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())
