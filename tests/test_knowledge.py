"""Tests for Knowledge feature (models, providers, and collection)."""

from __future__ import annotations

from typing import Optional

import httpx
import pytest

from xians.agents.knowledge.knowledge_collection import KnowledgeCollection
from xians.agents.knowledge.models import KnowledgeItem
from xians.agents.knowledge.providers.local_provider import LocalKnowledgeProvider
from xians.agents.knowledge.providers.server_provider import ServerKnowledgeProvider


class _StubProvider:
    """Simple in-memory provider stub for KnowledgeCollection tests."""

    def __init__(self) -> None:
        self.get_calls: list[tuple[str, str, Optional[str], Optional[str]]] = []
        self.update_calls: list[dict[str, object]] = []
        self.delete_calls: list[tuple[str, str, Optional[str], Optional[str]]] = []
        self.list_calls: list[tuple[str, Optional[str], Optional[str]]] = []
        self._get_results: list[Optional[KnowledgeItem]] = []
        self._system_results: list[Optional[KnowledgeItem]] = []

    def queue_get_result(self, item: Optional[KnowledgeItem]) -> None:
        self._get_results.append(item)

    def queue_system_result(self, item: Optional[KnowledgeItem]) -> None:
        self._system_results.append(item)

    async def get_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        self.get_calls.append((knowledge_name, agent_name, tenant_id, activation_name))
        if self._get_results:
            return self._get_results.pop(0)
        return None

    async def get_system_async(
        self,
        knowledge_name: str,
        agent_name: str,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        if self._system_results:
            return self._system_results.pop(0)
        return None

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
        self.update_calls.append(
            {
                "knowledge_name": knowledge_name,
                "content": content,
                "agent_name": agent_name,
                "tenant_id": tenant_id,
                "type": type,
                "system_scoped": system_scoped,
                "activation_name": activation_name,
                "description": description,
                "visible": visible,
            }
        )
        return True

    async def delete_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> bool:
        self.delete_calls.append((knowledge_name, agent_name, tenant_id, activation_name))
        return True

    async def list_async(
        self,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> list[KnowledgeItem]:
        self.list_calls.append((agent_name, tenant_id, activation_name))
        return [
            KnowledgeItem(
                name="one",
                content="1",
                type="text",
                agent=agent_name,
                tenant_id=tenant_id,
            )
        ]


class TestKnowledgeItem:
    def test_from_server_response_maps_camel_case(self) -> None:
        item = KnowledgeItem.from_server_response(
            {
                "id": "k1",
                "name": "system-instructions",
                "content": "hello",
                "type": "markdown",
                "tenantId": "t1",
                "systemScoped": False,
                "description": "desc",
                "visible": True,
            }
        )

        assert item.id == "k1"
        assert item.name == "system-instructions"
        assert item.content == "hello"
        assert item.type == "markdown"
        assert item.tenant_id == "t1"
        assert item.system_scoped is False
        assert item.description == "desc"
        assert item.visible is True

    def test_to_server_payload_maps_snake_to_camel(self) -> None:
        item = KnowledgeItem(
            name="cfg",
            content="{}",
            type="json",
            agent="AgentA",
            tenant_id="tenant1",
            system_scoped=True,
            description="config",
            visible=False,
        )

        payload = item.to_server_payload()
        assert payload["name"] == "cfg"
        assert payload["content"] == "{}"
        assert payload["type"] == "json"
        assert payload["agent"] == "AgentA"
        assert payload["tenantId"] == "tenant1"
        assert payload["systemScoped"] is True
        assert payload["description"] == "config"
        assert payload["visible"] is False


class TestLocalKnowledgeProvider:
    @pytest.mark.asyncio
    async def test_update_get_delete_roundtrip(self) -> None:
        provider = LocalKnowledgeProvider()

        ok = await provider.update_async(
            knowledge_name="welcome",
            content="hello",
            agent_name="AgentA",
            tenant_id="tenant1",
            type="text",
        )
        assert ok is True

        item = await provider.get_async("welcome", "AgentA", tenant_id="tenant1")
        assert item is not None
        assert item.content == "hello"
        assert item.agent == "AgentA"

        deleted = await provider.delete_async("welcome", "AgentA", tenant_id="tenant1")
        assert deleted is True
        assert await provider.get_async("welcome", "AgentA", tenant_id="tenant1") is None

    @pytest.mark.asyncio
    async def test_file_fallback_from_flat_knowledge_dir(self, tmp_path) -> None:
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        file_path = knowledge_dir / "system-instructions.md"
        file_path.write_text("from-file", encoding="utf-8")

        provider = LocalKnowledgeProvider(knowledge_dir=knowledge_dir)
        item = await provider.get_async("system-instructions", "AgentA")

        assert item is not None
        assert item.content == "from-file"
        assert item.type == "markdown"
        assert item.system_scoped is True

    @pytest.mark.asyncio
    async def test_file_fallback_from_agent_subfolder(self, tmp_path) -> None:
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        agent_dir = knowledge_dir / "AgentA"
        agent_dir.mkdir()
        file_path = agent_dir / "workflow-config.json"
        file_path.write_text('{"ok":true}', encoding="utf-8")

        provider = LocalKnowledgeProvider(knowledge_dir=knowledge_dir)
        item = await provider.get_async("workflow-config", "AgentA")

        assert item is not None
        assert item.content == '{"ok":true}'
        assert item.type == "json"

    @pytest.mark.asyncio
    async def test_uses_local_knowledge_folder_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        knowledge_dir = tmp_path / "kb"
        knowledge_dir.mkdir()
        (knowledge_dir / "system-instructions.txt").write_text("env-loaded", encoding="utf-8")
        monkeypatch.setenv("LOCAL_KNOWLEDGE_FOLDER", str(knowledge_dir))

        provider = LocalKnowledgeProvider()
        item = await provider.get_async("system-instructions", "AgentA")

        assert item is not None
        assert item.content == "env-loaded"
        assert item.type == "text"


class TestServerKnowledgeProvider:
    @pytest.mark.asyncio
    async def test_get_async_uses_cache(self) -> None:
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            return httpx.Response(
                status_code=200,
                json={"name": "k1", "content": "v1", "type": "text"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as client:
            provider = ServerKnowledgeProvider(client, cache_ttl_seconds=60, cache_enabled=True)
            first = await provider.get_async("k1", "AgentA", tenant_id="tenant1")
            second = await provider.get_async("k1", "AgentA", tenant_id="tenant1")

        assert first is not None and second is not None
        assert first.content == "v1"
        assert second.content == "v1"
        assert calls["count"] == 1

    @pytest.mark.asyncio
    async def test_get_async_returns_none_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as client:
            provider = ServerKnowledgeProvider(client)
            item = await provider.get_async("missing", "AgentA", tenant_id="tenant1")

        assert item is None

    @pytest.mark.asyncio
    async def test_update_invalidates_cached_get(self) -> None:
        calls = {"get": 0, "post": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path == "/api/agent/knowledge/latest":
                calls["get"] += 1
                content = "v1" if calls["get"] == 1 else "v2"
                return httpx.Response(
                    status_code=200,
                    json={"name": "k1", "content": content, "type": "text"},
                )
            if request.method == "POST" and request.url.path == "/api/agent/knowledge":
                calls["post"] += 1
                return httpx.Response(status_code=200, json={"ok": True})
            return httpx.Response(status_code=500)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as client:
            provider = ServerKnowledgeProvider(client, cache_ttl_seconds=60, cache_enabled=True)
            first = await provider.get_async("k1", "AgentA", tenant_id="tenant1")
            updated = await provider.update_async(
                knowledge_name="k1",
                content="updated",
                agent_name="AgentA",
                tenant_id="tenant1",
                type="text",
            )
            second = await provider.get_async("k1", "AgentA", tenant_id="tenant1")

        assert updated is True
        assert first is not None and first.content == "v1"
        assert second is not None and second.content == "v2"
        assert calls["post"] == 1
        assert calls["get"] == 2


class TestKnowledgeCollection:
    @pytest.mark.asyncio
    async def test_get_async_replicates_system_item_for_tenant(self) -> None:
        provider = _StubProvider()
        provider.queue_get_result(
            KnowledgeItem(
                name="system-instructions",
                content="from-system",
                type="markdown",
                system_scoped=True,
                visible=True,
            )
        )
        provider.queue_get_result(
            KnowledgeItem(
                name="system-instructions",
                content="tenant-copy",
                type="markdown",
                system_scoped=False,
                visible=True,
            )
        )

        collection = KnowledgeCollection(
            agent_name="AgentA",
            provider=provider,
            tenant_id="tenant1",
            system_scoped=False,
        )
        item = await collection.get_async("system-instructions")

        assert item is not None
        assert item.content == "tenant-copy"
        assert len(provider.update_calls) == 1
        assert provider.update_calls[0]["tenant_id"] == "tenant1"
        assert provider.update_calls[0]["system_scoped"] is False

    @pytest.mark.asyncio
    async def test_upload_from_file_infers_name_and_type(self, tmp_path) -> None:
        provider = _StubProvider()
        collection = KnowledgeCollection(
            agent_name="AgentA",
            provider=provider,
            tenant_id="tenant1",
            system_scoped=False,
        )

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        file_path = knowledge_dir / "Workflow Instructions.md"
        file_path.write_text("prompt-content", encoding="utf-8")

        ok = await collection.upload_from_file(file_path)

        assert ok is True
        assert len(provider.update_calls) == 1
        call = provider.update_calls[0]
        assert call["knowledge_name"] == "Workflow Instructions"
        assert call["content"] == "prompt-content"
        assert call["type"] == "markdown"

    @pytest.mark.asyncio
    async def test_upload_from_file_missing_path_returns_false(self) -> None:
        provider = _StubProvider()
        collection = KnowledgeCollection(
            agent_name="AgentA",
            provider=provider,
            tenant_id="tenant1",
            system_scoped=False,
        )

        ok = await collection.upload_from_file("does-not-exist.md")

        assert ok is False
        assert provider.update_calls == []
