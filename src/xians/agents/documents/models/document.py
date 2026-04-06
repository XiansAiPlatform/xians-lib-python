"""Document model. Matches C# Xians.Lib.Agents.Documents.Models.Document."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Represents a document stored in the agent's document database.

    Documents are scoped to the agent and can store any JSON-serializable content.
    Matches C# Document model.
    """

    id: Optional[str] = Field(None, alias="id")
    key: Optional[str] = Field(None, alias="key")
    content: Optional[Any] = Field(None, alias="content")
    metadata: Optional[dict[str, Any]] = Field(None, alias="metadata")
    type: Optional[str] = Field(None, alias="type")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    expires_at: Optional[datetime] = Field(None, alias="expiresAt")
    agent_id: Optional[str] = Field(None, alias="agentId")
    workflow_id: Optional[str] = Field(None, alias="workflowId")
    created_by: Optional[str] = Field(None, alias="createdBy")
    updated_by: Optional[str] = Field(None, alias="updatedBy")
    activation_name: Optional[str] = Field(None, alias="activationName")
    participant_id: Optional[str] = Field(None, alias="participantId")

    model_config = {
        "populate_by_name": True,
        "json_encoders": {datetime: lambda v: v.isoformat() if v else None},
    }

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to camelCase dict for API calls.

        Uses mode="json" so datetime fields are converted to ISO strings
        rather than raw datetime objects (which stdlib json can't serialize).
        """
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> Document:
        """Deserialize from camelCase API response."""
        return cls.model_validate(data)


__all__ = ["Document"]
