"""OpenAI adapter implementation."""

from src.interfaces.v1 import ILLMAdapter
from src.models.v1 import LLMConfig, LLMMessage, LLMResponse


class OpenAIAdapter(ILLMAdapter):
    """LLM adapter for OpenAI."""

    async def chat(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        _ = (messages, config)
        return LLMResponse(
            text="OpenAI response placeholder",
            model=config.model,
            finish_reason="stop",
            usage={},
        )

    async def validate_config(self, config: LLMConfig) -> None:
        _ = config
        return None

    async def get_provider_name(self) -> str:
        return "openai"


__all__ = ["OpenAIAdapter"]
