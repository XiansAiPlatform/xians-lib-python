"""
Web Search Sub-Agent — LangChain ReAct agent with DuckDuckGo web search tools.

This is the Python equivalent of the C# SecretsSubAgent / HealthcareSubAgent
pattern: a sub-agent class that wraps a framework (LangChain) and is invoked
from the Xians workflow handler via `run_async(context)`.

Architecture:
    Xians BuiltinWorkflow
      → on_user_chat_message(handler)
        → WebSearchSubAgent.run_async(context)
          → Loads system instructions from Knowledge (local .md file or server)
          → LangGraph ReAct agent with tools
            → DuckDuckGo web search (free, no API key needed)
            → Current date/time tool
          → returns answer string
        → context.reply_async(answer)
"""

import logging
from datetime import datetime, timezone

from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from xians.agents.core import XiansContext

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_INSTRUCTIONS = """\
You are a helpful web search assistant. Your job is to help users find accurate,
up-to-date information from the internet.
"""


def _build_tools() -> list:
    """Build the tool list for the ReAct agent."""

    ddg_search = DuckDuckGoSearchResults(
        max_results=5,
        output_format="list",
    )

    @tool
    def current_datetime() -> str:
        """Get the current date and time in UTC. Use this when users ask about
        the current date, time, or when they need time-sensitive context."""
        now = datetime.now(timezone.utc)
        return now.strftime("%A, %B %d, %Y at %I:%M %p UTC")

    return [ddg_search, current_datetime]


class WebSearchSubAgent:
    """LangChain-based web search sub-agent using DuckDuckGo.

    Loads system instructions from Xians Knowledge (local file or server)
    at runtime, falling back to a default prompt if not found.

    Mirrors the C# sub-agent pattern:
        var agent = new SecretsSubAgent(openAiApiKey, xiansAgent);
        var response = await agent.RunAsync(context);

    Python equivalent:
        agent = WebSearchSubAgent(openai_api_key)
        response = await agent.run_async(context)

    Knowledge setup (local mode):
        Place a markdown file at:
          knowledge/{AgentName}/system-instructions.md
        And set KNOWLEDGE_DIR=./knowledge in your .env
    """

    def __init__(
        self,
        openai_api_key: str,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ):
        self._openai_api_key = openai_api_key
        self._model_name = model_name
        self._temperature = temperature
        self._tools = _build_tools()
        self._cached_agent = None
        self._cached_prompt: str | None = None

    async def _get_system_instructions(self) -> str:
        """Load system instructions from Knowledge, with fallback."""
        try:
            agent = XiansContext.CurrentAgent
            knowledge = await agent.knowledge.get_async("system-instructions")
            if knowledge and knowledge.content:
                logger.info("Loaded system instructions from Knowledge")
                return knowledge.content
        except Exception as e:
            logger.warning("Could not load knowledge: %s — using default prompt", e)

        return DEFAULT_SYSTEM_INSTRUCTIONS

    async def _get_or_create_agent(self, system_instructions: str):
        """Create or reuse the LangGraph agent (recreate if prompt changed)."""
        if self._cached_agent is not None and self._cached_prompt == system_instructions:
            return self._cached_agent

        llm = ChatOpenAI(
            model=self._model_name,
            temperature=self._temperature,
            api_key=self._openai_api_key,
        )
        self._cached_agent = create_react_agent(
            llm,
            tools=self._tools,
            prompt=system_instructions,
        )
        self._cached_prompt = system_instructions
        return self._cached_agent

    async def run_async(self, context) -> str:
        """Run the agent on a user message from the Xians workflow context.

        Loads system instructions from Knowledge on each invocation
        (cached after first load). Falls back to a default prompt.

        Args:
            context: UserMessageContext from the Xians BuiltinWorkflow handler.

        Returns:
            The agent's text response.
        """
        user_text = context.message.text
        if not user_text or not user_text.strip():
            return (
                "I didn't receive a message. I can help you search the web for "
                "any topic — just ask me a question!"
            )

        logger.info(f"Processing search query: {user_text[:80]}...")

        try:
            system_instructions = await self._get_system_instructions()
            agent = await self._get_or_create_agent(system_instructions)

            result = await agent.ainvoke(
                {"messages": [("user", user_text)]}
            )

            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                response_text = (
                    last_message.content
                    if hasattr(last_message, "content")
                    else str(last_message)
                )
                return response_text

            return "I wasn't able to generate a response. Please try rephrasing your question."

        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            return f"I encountered an error while searching: {str(e)}"
