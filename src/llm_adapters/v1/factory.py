"""Factory for creating LLM adapters."""

from src.constants.v1 import LLMProvider
from src.interfaces.v1 import ILLMAdapter

from .anthropic_adapter import AnthropicAdapter
from .bedrock_adapter import BedrockAdapter
from .microsoft_agent_adapter import MicrosoftAgentAdapter
from .openai_adapter import OpenAIAdapter
from .vertex_adapter import VertexAIAdapter


def create_llm_adapter(provider: LLMProvider) -> ILLMAdapter:
    """Create an LLM adapter instance for the given provider."""
    if provider == LLMProvider.OPENAI:
        return OpenAIAdapter()
    if provider == LLMProvider.ANTHROPIC:
        return AnthropicAdapter()
    if provider == LLMProvider.GOOGLE_VERTEX:
        return VertexAIAdapter()
    if provider == LLMProvider.MICROSOFT_AGENT:
        return MicrosoftAgentAdapter()
    if provider == LLMProvider.AWS_BEDROCK:
        return BedrockAdapter()
    raise ValueError(f"Unsupported LLM provider: {provider}")


__all__ = ["create_llm_adapter"]
