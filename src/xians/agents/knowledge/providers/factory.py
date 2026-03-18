"""Knowledge provider factory. Matches C# KnowledgeProviderFactory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

import httpx

from .local_provider import LocalKnowledgeProvider
from .server_provider import ServerKnowledgeProvider

if TYPE_CHECKING:
    from .interface import KnowledgeProvider

logger = logging.getLogger(__name__)


class KnowledgeProviderFactory:
    """Selects the appropriate KnowledgeProvider based on runtime options.

    Mirrors C# KnowledgeProviderFactory.Create():
    - local_mode=True  → LocalKnowledgeProvider
    - otherwise        → ServerKnowledgeProvider (requires an httpx.AsyncClient)
    """

    @staticmethod
    def create(
        *,
        local_mode: bool = False,
        http_client: Optional[httpx.AsyncClient] = None,
        knowledge_dir: Optional[Union[str, Path]] = None,
        cache_ttl_seconds: float = 600,
        cache_enabled: bool = True,
    ) -> "KnowledgeProvider":
        if local_mode:
            logger.info("Using LocalKnowledgeProvider (local_mode=True)")
            return LocalKnowledgeProvider(knowledge_dir=knowledge_dir)

        if http_client is None:
            raise ValueError(
                "An httpx.AsyncClient is required when local_mode is False. "
                "Ensure the platform HTTP client has been initialized."
            )

        logger.info("Using ServerKnowledgeProvider")
        return ServerKnowledgeProvider(
            http_client=http_client,
            cache_ttl_seconds=cache_ttl_seconds,
            cache_enabled=cache_enabled,
        )
