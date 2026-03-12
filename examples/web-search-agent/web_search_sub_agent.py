"""
Web Search Sub-Agent — LangChain ReAct agent with DuckDuckGo web search tools.

This is the Python equivalent of the C# SecretsSubAgent / HealthcareSubAgent
pattern: a sub-agent class that wraps a framework (LangChain) and is invoked
from the Xians workflow handler via `run_async(context)`.

Architecture:
    Xians BuiltinWorkflow
      → on_user_chat_message(handler)
        → WebSearchSubAgent.run_async(context)
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

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """\
You are a helpful web search assistant. Your job is to help users find accurate,
up-to-date information from the internet.

Guidelines:
- Use the web search tool to find current information before answering.
- Always cite your sources by including the URL where you found the information.
- If the search doesn't return relevant results, let the user know and suggest
  refining their query.
- For time-sensitive questions, always search rather than relying on your training data.
- Summarize information clearly and concisely.
- If the user asks a follow-up question, consider the conversation context.
- Use the current_datetime tool when the user asks about the current date or time.
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

    Mirrors the C# sub-agent pattern:
        var agent = new SecretsSubAgent(openAiApiKey, xiansAgent);
        var response = await agent.RunAsync(context);

    Python equivalent:
        agent = WebSearchSubAgent(openai_api_key)
        response = await agent.run_async(context)
    """

    def __init__(
        self,
        openai_api_key: str,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ):
        self._llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=openai_api_key,
        )
        self._tools = _build_tools()
        self._agent = create_react_agent(
            self._llm,
            tools=self._tools,
            prompt=SYSTEM_INSTRUCTIONS,
        )

    async def run_async(self, context) -> str:
        """Run the agent on a user message from the Xians workflow context.

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
            result = await self._agent.ainvoke(
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
