from abc import ABC, abstractmethod

from src.models.v1 import LLMConfig, LLMMessage, LLMResponse


class ILLMAdapter(ABC):
    """Interface for LLM provider adapters."""

    @abstractmethod
    async def chat(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        """Perform a chat/completions request and return the response."""
        raise NotImplementedError

    @abstractmethod
    async def validate_config(self, config: LLMConfig) -> None:
        """Validate provider-specific configuration."""
        raise NotImplementedError

    @abstractmethod
    async def get_provider_name(self) -> str:
        """Return the provider identifier (e.g., 'openai')."""
        raise NotImplementedError


__all__ = ["ILLMAdapter"]
