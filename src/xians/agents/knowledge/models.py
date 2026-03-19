"""Knowledge data models. Matches C# Xians.Lib.Agents.Knowledge.Models.Knowledge."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """Represents a single knowledge entry.

    Matches the C# Knowledge model and the server's JSON contract.
    """

    id: Optional[str] = Field(default=None, description="Server-assigned identifier")
    name: str = Field(description="Knowledge name (key)")
    version: Optional[str] = Field(default=None, description="Version string")
    content: str = Field(description="Knowledge content body")
    type: Optional[str] = Field(
        default=None,
        description="Content type: text, markdown, json, xml, yaml",
    )
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    agent: Optional[str] = Field(default=None, description="Owning agent name")
    tenant_id: Optional[str] = Field(default=None, description="Tenant scope")
    system_scoped: bool = Field(default=False, description="True = shared across all tenants")
    description: Optional[str] = Field(default=None, description="Human-readable description")
    visible: bool = Field(default=True, description="Whether visible in listings")

    model_config = {"frozen": False, "populate_by_name": True}

    @classmethod
    def from_server_response(cls, data: dict[str, Any]) -> "KnowledgeItem":
        """Parse a KnowledgeItem from the server's camelCase JSON."""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            version=data.get("version"),
            content=data.get("content", ""),
            type=data.get("type"),
            created_at=data.get("createdAt"),
            agent=data.get("agent"),
            tenant_id=data.get("tenantId"),
            system_scoped=data.get("systemScoped", False),
            description=data.get("description"),
            visible=data.get("visible", True),
        )

    def to_server_payload(self) -> dict[str, Any]:
        """Serialize to the server's expected camelCase JSON for create/update."""
        payload: dict[str, Any] = {
            "name": self.name,
            "content": self.content,
        }
        if self.type is not None:
            payload["type"] = self.type
        if self.agent is not None:
            payload["agent"] = self.agent
        if self.tenant_id is not None:
            payload["tenantId"] = self.tenant_id
        if self.description is not None:
            payload["description"] = self.description
        payload["systemScoped"] = self.system_scoped
        payload["visible"] = self.visible
        return payload


__all__ = ["KnowledgeItem"]
