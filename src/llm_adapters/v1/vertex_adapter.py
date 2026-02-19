"""Vertex AI adapter implementation."""

from src.interfaces.v1 import ILLMAdapter
from src.models.v1 import LLMConfig, LLMMessage, LLMResponse


class VertexAIAdapter(ILLMAdapter):
    """LLM adapter for Google Vertex AI."""

    async def chat(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        _ = (messages, config)
        # Placeholder implementation; integrate Vertex AI SDK or HTTP client here
        return LLMResponse(
            text="Vertex AI response placeholder",
            model=config.model,
            finish_reason="stop",
            usage={},
        )

    async def validate_config(self, config: LLMConfig) -> None:
        _ = config
        # Add provider-specific validation as needed
        return None

    async def get_provider_name(self) -> str:
        return "google_vertex"


__all__ = ["VertexAIAdapter"]
