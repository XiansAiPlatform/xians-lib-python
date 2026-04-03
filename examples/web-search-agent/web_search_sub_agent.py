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


def _extract_token_usage(message) -> tuple[int, int, int] | None:
    """Extract prompt, completion, and total tokens from LangChain message.

    Handles usage_metadata (LangChain standard) and response_metadata (OpenAI).
    """
    def _get(obj, *keys) -> int | None:
        if obj is None:
            return None
        for k in keys:
            v = getattr(obj, k, None) if hasattr(obj, k) else (obj.get(k) if isinstance(obj, dict) else None)
            if v is not None:
                return int(v)
        return None

    # usage_metadata: input_tokens, output_tokens, total_tokens
    um = getattr(message, "usage_metadata", None)
    if um:
        prompt = _get(um, "input_tokens")
        completion = _get(um, "output_tokens")
        if prompt is not None or completion is not None:
            total = _get(um, "total_tokens") or (prompt or 0) + (completion or 0)
            return (prompt or 0, completion or 0, total)

    # response_metadata: token_usage or usage (OpenAI-style)
    rm = getattr(message, "response_metadata", None) or {}
    tu = rm.get("token_usage") or rm.get("usage") or {}
    if tu:
        prompt = _get(tu, "prompt_tokens", "input_tokens", "input_text_tokens")
        completion = _get(tu, "completion_tokens", "output_tokens")
        if prompt is not None or completion is not None:
            total = _get(tu, "total_tokens") or (prompt or 0) + (completion or 0)
            return (prompt or 0, completion or 0, total)

    return None


async def _report_llm_metrics(context, message) -> None:
    """Report LLM token usage to Xians metrics."""
    usage = _extract_token_usage(message)
    if not usage:
        return

    prompt_tokens, completion_tokens, total_tokens = usage
    model = getattr(message, "response_metadata", {}) or {}
    if isinstance(model, dict):
        model_name = model.get("model_name") or model.get("model") or "gpt-4o-mini"
    else:
        model_name = "gpt-4o-mini"

    try:
        await context.metrics \
            .for_model(model_name) \
            .with_metrics(
                ("tokens", "prompt", prompt_tokens, "tokens"),
                ("tokens", "completion", completion_tokens, "tokens"),
                ("tokens", "total", total_tokens, "tokens"),
            ) \
            .report_async()
        logger.debug("Reported LLM metrics: prompt=%s completion=%s total=%s", prompt_tokens, completion_tokens, total_tokens)
    except Exception as ex:
        logger.warning("Failed to report LLM metrics: %s", ex)

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

        Streams reasoning and tool execution progress messages to the user
        while the agent works, then returns the final answer.

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
            # Stream reasoning progress to user (Message Progress feature)
            await context.send_reasoning_async(
                f"Analyzing query: {user_text[:60]}..."
            )

            system_instructions = await self._get_system_instructions()
            agent = await self._get_or_create_agent(system_instructions)

            await context.send_reasoning_async(
                "Determining search strategy and selecting tools..."
            )

            result = await agent.ainvoke(
                {"messages": [("user", user_text)]}
            )

            messages = result.get("messages", [])

            # Stream tool execution progress for any tool calls in the message history
            for msg in messages:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get("name", "unknown") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                        await context.send_tool_exec_async(
                            f"{tool_name}(...)"
                        )

            if messages:
                last_message = messages[-1]
                response_text = (
                    last_message.content
                    if hasattr(last_message, "content")
                    else str(last_message)
                )

                await _report_llm_metrics(context, last_message)

                await context.send_reasoning_async(
                    "Synthesizing search results into a response..."
                )

                return response_text

            return "I wasn't able to generate a response. Please try rephrasing your question."

        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            return f"I encountered an error while searching: {str(e)}"
