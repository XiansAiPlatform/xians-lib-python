"""Server-backed knowledge provider. Matches C# ServerKnowledgeProvider.

All knowledge operations are forwarded to the Xians Server via HTTP.
Supports optional in-memory caching with configurable TTL.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from ..models import KnowledgeItem

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 600  # 10 minutes, matches C# default


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class ServerKnowledgeProvider:
    """HTTP-backed knowledge provider. Matches C# ServerKnowledgeProvider.

    API endpoints:
      GET    /api/agent/knowledge/latest        (tenant-scoped, progressive fallback)
      GET    /api/agent/knowledge/latest/system  (system-scoped)
      POST   /api/agent/knowledge               (create / update)
      DELETE /api/agent/knowledge                (delete)
      GET    /api/agent/knowledge/list           (list)
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        cache_enabled: bool = True,
    ) -> None:
        self._client = http_client
        self._cache_ttl = cache_ttl_seconds
        self._cache_enabled = cache_enabled
        self._cache: dict[str, _CacheEntry] = {}

    # ------------------------------------------------------------------
    # IKnowledgeProvider
    # ------------------------------------------------------------------

    async def get_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        cache_key = self._cache_key(tenant_id, agent_name, activation_name, knowledge_name)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str] = {"name": knowledge_name, "agent": agent_name}
        if activation_name:
            params["activationName"] = activation_name

        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id

        try:
            response = await self._client.get(
                "/api/agent/knowledge/latest",
                params=params,
                headers=headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            item = KnowledgeItem.from_server_response(data)
            self._set_cached(cache_key, item)
            return item
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            logger.error("Failed to get knowledge '%s': %s", knowledge_name, exc)
            raise

    async def get_system_async(
        self,
        knowledge_name: str,
        agent_name: str,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        cache_key = self._cache_key("system", agent_name, activation_name, knowledge_name)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str] = {"name": knowledge_name, "agent": agent_name}
        if activation_name:
            params["activationName"] = activation_name

        try:
            response = await self._client.get(
                "/api/agent/knowledge/latest/system",
                params=params,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            item = KnowledgeItem.from_server_response(data)
            self._set_cached(cache_key, item)
            return item
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            logger.error("Failed to get system knowledge '%s': %s", knowledge_name, exc)
            raise

    async def update_async(
        self,
        knowledge_name: str,
        content: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        type: Optional[str] = None,
        system_scoped: bool = False,
        activation_name: Optional[str] = None,
        description: Optional[str] = None,
        visible: bool = True,
    ) -> bool:
        payload: dict[str, Any] = {
            "name": knowledge_name,
            "content": content,
            "agent": agent_name,
            "systemScoped": system_scoped,
            "visible": visible,
        }
        if type is not None:
            payload["type"] = type
        if tenant_id is not None:
            payload["tenantId"] = tenant_id
        if description is not None:
            payload["description"] = description

        params: dict[str, str] = {}
        if activation_name:
            params["activationName"] = activation_name

        try:
            response = await self._client.post(
                "/api/agent/knowledge",
                json=payload,
                params=params if params else None,
            )
            response.raise_for_status()
            self._invalidate_cache(tenant_id, agent_name, activation_name, knowledge_name)
            return True
        except Exception:
            logger.error("Failed to update knowledge '%s'", knowledge_name, exc_info=True)
            return False

    async def delete_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> bool:
        params: dict[str, str] = {"name": knowledge_name, "agent": agent_name}
        if activation_name:
            params["activationName"] = activation_name

        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id

        try:
            response = await self._client.delete(
                "/api/agent/knowledge",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            self._invalidate_cache(tenant_id, agent_name, activation_name, knowledge_name)
            return True
        except Exception:
            logger.error("Failed to delete knowledge '%s'", knowledge_name, exc_info=True)
            return False

    async def list_async(
        self,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> list[KnowledgeItem]:
        params: dict[str, str] = {"agent": agent_name}
        if activation_name:
            params["activationName"] = activation_name

        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id

        try:
            response = await self._client.get(
                "/api/agent/knowledge/list",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            items = data if isinstance(data, list) else []
            return [KnowledgeItem.from_server_response(item) for item in items]
        except Exception:
            logger.error("Failed to list knowledge for agent '%s'", agent_name, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Cache helpers (mirrors C# CacheService.GetKnowledge / SetKnowledge)
    # ------------------------------------------------------------------

    def _cache_key(
        self,
        tenant_id: Optional[str],
        agent_name: str,
        activation_name: Optional[str],
        knowledge_name: str,
    ) -> str:
        return f"knowledge:{tenant_id or ''}:{agent_name}:{activation_name or ''}:{knowledge_name}"

    def _get_cached(self, key: str) -> Optional[KnowledgeItem]:
        if not self._cache_enabled:
            return None
        entry = self._cache.get(key)
        if entry is None or entry.expired:
            self._cache.pop(key, None)
            return None
        return entry.value

    def _set_cached(self, key: str, item: KnowledgeItem) -> None:
        if self._cache_enabled:
            self._cache[key] = _CacheEntry(item, self._cache_ttl)

    def _invalidate_cache(
        self,
        tenant_id: Optional[str],
        agent_name: str,
        activation_name: Optional[str],
        knowledge_name: str,
    ) -> None:
        key = self._cache_key(tenant_id, agent_name, activation_name, knowledge_name)
        self._cache.pop(key, None)
        system_key = self._cache_key("system", agent_name, activation_name, knowledge_name)
        self._cache.pop(system_key, None)
