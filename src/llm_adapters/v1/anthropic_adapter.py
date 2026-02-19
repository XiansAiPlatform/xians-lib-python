"""Anthropic adapter implementation."""

from src.interfaces.v1 import ILLMAdapter
from src.models.v1 import LLMConfig, LLMMessage, LLMResponse


class AnthropicAdapter(ILLMAdapter):
    """LLM adapter for Anthropic."""

    async def chat(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        _ = (messages, config)
        return LLMResponse(
            text="Anthropic response placeholder",
            model=config.model,
            finish_reason="stop",
            usage={},
        )

    async def validate_config(self, config: LLMConfig) -> None:
        _ = config
        return None

    async def get_provider_name(self) -> str:
        return "anthropic"


__all__ = ["AnthropicAdapter"]
