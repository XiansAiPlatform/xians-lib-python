"""Abstract knowledge provider interface. Matches C# IKnowledgeProvider."""

from __future__ import annotations

from typing import Optional, Protocol

from ..models import KnowledgeItem


class KnowledgeProvider(Protocol):
    """Protocol defining the contract every knowledge provider must satisfy.

    Mirrors C# IKnowledgeProvider with identical method signatures
    (adapted to Python conventions).
    """

    async def get_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        """Retrieve tenant-scoped knowledge by name (progressive fallback on server)."""
        ...

    async def get_system_async(
        self,
        knowledge_name: str,
        agent_name: str,
        activation_name: Optional[str] = None,
    ) -> Optional[KnowledgeItem]:
        """Retrieve system-scoped knowledge by name."""
        ...

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
        """Create or update a knowledge entry. Returns True on success."""
        ...

    async def delete_async(
        self,
        knowledge_name: str,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> bool:
        """Delete a knowledge entry. Returns True on success."""
        ...

    async def list_async(
        self,
        agent_name: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> list[KnowledgeItem]:
        """List all knowledge entries for an agent."""
        ...
