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

Prerequisites:
    pip install langchain-openai langchain-community duckduckgo-search langgraph

Environment variables (.env):
    OPENAI_API_KEY=sk-...
    XIANS_SERVER_URL=https://api.agentri.ai
    XIANS_API_KEY=<base64 certificate>
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration

from web_search_sub_agent import WebSearchSubAgent


async def main() -> None:
    load_dotenv()

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    server_url = os.environ.get("XIANS_SERVER_URL")
    xians_api_key = os.environ.get("XIANS_API_KEY")

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
        )
    )

    # ── Step 2: Register agent (matches C# xiansPlatform.Agents.Register) ──
    xians_agent = xians_platform.agents.register(
        XiansAgentRegistration(
            name="Web Search Agent6",
            description=(
                "AI-powered web search assistant that finds and summarizes "
                "real-time information from the internet using Tavily search."
            ),
            summary="Web search agent with LangChain tools",
            version="1.0.2",
            author="99x",
            is_template=True,
        )
    )

    # ── Step 3: Define workflow (matches C# DefineBuiltIn) ──
    conversational_workflow = xians_agent.define_builtin_workflow(
        name="Supervisor Workflow"
    )

    # ── Step 4: Create sub-agent (the LangChain agent with tools) ──
    search_sub_agent = WebSearchSubAgent(
        openai_api_key=openai_api_key,
    )

    # ── Step 5: Wire up handler (matches C# OnUserChatMessage) ──
    async def handle_chat(context):
        response = await search_sub_agent.run_async(context)
        await context.reply_async(response)

    conversational_workflow.on_user_chat_message(handle_chat)

    # ── Step 6: Start (matches C# RunAllAsync) ──
    await xians_agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())
