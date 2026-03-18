"""KnowledgeCollection - public facade for agent knowledge operations.

Matches C# Xians.Lib.Agents.Knowledge.KnowledgeCollection.
This is the object exposed as ``agent.knowledge`` (and therefore
``XiansContext.CurrentAgent.knowledge``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .models import KnowledgeItem
from .providers.interface import KnowledgeProvider

logger = logging.getLogger(__name__)


class KnowledgeCollection:
    """Public API for knowledge CRUD scoped to a single agent.

    Mirrors C# KnowledgeCollection which is exposed as ``agent.Knowledge``.

    Key behaviors matching C#:
    - get_async: retrieves tenant-scoped knowledge with progressive fallback
      (instance → tenant → system). If the server returns system-scoped
      knowledge for a tenant-scoped agent, a tenant replica is created
      automatically.
    - update_async / delete_async: mutate knowledge entries.
    - list_async: returns all knowledge for this agent.
    """

    def __init__(
        self,
        agent_name: str,
        provider: KnowledgeProvider,
        tenant_id: Optional[str] = None,
        system_scoped: bool = False,
    ) -> None:
        self._agent_name = agent_name
        self._provider = provider
        self._tenant_id = tenant_id
        self._system_scoped = system_scoped
        self._local_knowledge: dict[str, KnowledgeItem] = {}

    @property
    def agent_name(self) -> str:
        return self._agent_name

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    async def get_async(self, knowledge_name: str) -> Optional[KnowledgeItem]:
        """Retrieve knowledge by name.

        Uses progressive fallback on the server side:
        instance → tenant → system.

        If the returned item is system-scoped but this agent is tenant-scoped,
        a tenant copy is created automatically (mirrors C# behavior).
        """
        tenant_id = self._resolve_tenant_id()

        item = await self._provider.get_async(
            knowledge_name=knowledge_name,
            agent_name=self._agent_name,
            tenant_id=tenant_id,
        )

        if item is not None and item.system_scoped and not self._system_scoped and tenant_id:
            await self._provider.update_async(
                knowledge_name=knowledge_name,
                content=item.content,
                agent_name=self._agent_name,
                tenant_id=tenant_id,
                type=item.type,
                system_scoped=False,
                description=item.description,
                visible=item.visible,
            )
            item = await self._provider.get_async(
                knowledge_name=knowledge_name,
                agent_name=self._agent_name,
                tenant_id=tenant_id,
            )

        if item is not None:
            self._local_knowledge[knowledge_name] = item

        return item

    async def get_system_async(self, knowledge_name: str) -> Optional[KnowledgeItem]:
        """Retrieve system-scoped knowledge by name (no tenant header)."""
        item = await self._provider.get_system_async(
            knowledge_name=knowledge_name,
            agent_name=self._agent_name,
        )
        if item is not None:
            self._local_knowledge[knowledge_name] = item
        return item

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_async(
        self,
        knowledge_name: str,
        content: str,
        type: Optional[str] = None,
        system_scoped: Optional[bool] = None,
        description: Optional[str] = None,
        visible: bool = True,
    ) -> bool:
        """Create or update a knowledge entry."""
        tenant_id = self._resolve_tenant_id()
        is_system = system_scoped if system_scoped is not None else self._system_scoped

        success = await self._provider.update_async(
            knowledge_name=knowledge_name,
            content=content,
            agent_name=self._agent_name,
            tenant_id=tenant_id,
            type=type,
            system_scoped=is_system,
            description=description,
            visible=visible,
        )

        if success:
            self._local_knowledge[knowledge_name] = KnowledgeItem(
                name=knowledge_name,
                content=content,
                type=type,
                agent=self._agent_name,
                tenant_id=tenant_id,
                system_scoped=is_system,
                description=description,
                visible=visible,
            )

        return success

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_async(self, knowledge_name: str) -> bool:
        """Delete a knowledge entry."""
        tenant_id = self._resolve_tenant_id()
        success = await self._provider.delete_async(
            knowledge_name=knowledge_name,
            agent_name=self._agent_name,
            tenant_id=tenant_id,
        )
        if success:
            self._local_knowledge.pop(knowledge_name, None)
        return success

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_async(self) -> list[KnowledgeItem]:
        """List all knowledge entries for this agent."""
        tenant_id = self._resolve_tenant_id()
        items = await self._provider.list_async(
            agent_name=self._agent_name,
            tenant_id=tenant_id,
        )
        for item in items:
            self._local_knowledge[item.name] = item
        return items

    # ------------------------------------------------------------------
    # Display (mirrors C# DisplayKnowledgeSummaryAsync)
    # ------------------------------------------------------------------

    async def display_summary_async(self) -> None:
        """Print a formatted summary of cached knowledge to the logger."""
        if not self._local_knowledge:
            logger.info("[Knowledge] No knowledge loaded for agent '%s'", self._agent_name)
            return

        logger.info("[Knowledge] Summary for agent '%s':", self._agent_name)
        for name, item in self._local_knowledge.items():
            scope = "system" if item.system_scoped else "tenant"
            visible = "visible" if item.visible else "hidden"
            preview = (item.content[:80] + "...") if len(item.content) > 80 else item.content
            logger.info(
                "  - %s [%s, %s, %s]: %s",
                name,
                item.type or "unknown",
                scope,
                visible,
                preview,
            )

    # ------------------------------------------------------------------
    # Upload from file (mirrors C# EmbeddedKnowledgeLoader)
    # ------------------------------------------------------------------

    _EXT_TO_TYPE = {
        ".md": "markdown",
        ".txt": "text",
        ".json": "json",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
    }

    async def upload_from_file(
        self,
        resource_path: str | Path,
        knowledge_name: Optional[str] = None,
        knowledge_type: Optional[str] = None,
        system_scoped: Optional[bool] = None,
        description: Optional[str] = None,
        visible: bool = True,
    ) -> bool:
        """Upload a local file as knowledge. Mirrors C# UploadEmbeddedResourceAsync.

        This is the primary pattern for uploading knowledge at agent startup:

            await agent.knowledge.upload_from_file(
                "knowledge/System Instructions.md",
                knowledge_name="system-instructions",
                description="Main system prompt",
            )

        Args:
            resource_path: Path to the file (relative or absolute).
            knowledge_name: Knowledge key. If None, inferred from filename
                            (e.g. "System Instructions.md" → "System Instructions").
            knowledge_type: Content type. If None, inferred from extension.
            system_scoped: Override scope. If None, uses agent's scope.
            description: Human-readable description.
            visible: Whether visible in listings.
        """
        path = Path(resource_path)
        if not path.is_file():
            logger.error("Knowledge file not found: %s", path.resolve())
            return False

        if knowledge_name is None:
            knowledge_name = path.stem

        if knowledge_type is None:
            knowledge_type = self._EXT_TO_TYPE.get(path.suffix.lower(), "text")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            logger.error("Failed to read knowledge file: %s", path, exc_info=True)
            return False

        return await self.update_async(
            knowledge_name=knowledge_name,
            content=content,
            type=knowledge_type,
            system_scoped=system_scoped,
            description=description,
            visible=visible,
        )

    async def upload_text(
        self,
        knowledge_name: str,
        content: str,
        knowledge_type: Optional[str] = None,
        visible: bool = True,
        description: Optional[str] = None,
    ) -> bool:
        """Upload raw text as knowledge. Mirrors C# UploadTextResourceAsync."""
        return await self.update_async(
            knowledge_name=knowledge_name,
            content=content,
            type=knowledge_type,
            description=description,
            visible=visible,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_tenant_id(self) -> Optional[str]:
        """Resolve tenant ID. Mirrors C# KnowledgeCollection.GetTenantId().

        For system-scoped agents, tenant is always None.
        Otherwise use the tenant_id provided at construction or fall back
        to XiansContext.get_tenant_id().
        """
        if self._system_scoped:
            return None
        if self._tenant_id:
            return self._tenant_id

        from ..core.xians_context import XiansContext
        return XiansContext.get_tenant_id()
