"""DocumentQuery model. Matches C# Xians.Lib.Agents.Documents.Models.DocumentQuery."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentQuery(BaseModel):
    """Query parameters for searching documents.

    All filters are combined with AND logic.
    Matches C# DocumentQuery.
    """

    type: Optional[str] = Field(None, alias="type")
    key: Optional[str] = Field(None, alias="key")
    agent_id: Optional[str] = Field(None, alias="agentId")
    activation_name: Optional[str] = Field(None, alias="activationName")
    participant_id: Optional[str] = Field(None, alias="participantId")
    metadata_filters: Optional[dict[str, Any]] = Field(None, alias="metadataFilters")
    limit: Optional[int] = Field(100, alias="limit")
    skip: Optional[int] = Field(0, alias="skip")
    sort_by: Optional[str] = Field(None, alias="sortBy")
    sort_descending: bool = Field(True, alias="sortDescending")
    created_after: Optional[datetime] = Field(None, alias="createdAfter")
    created_before: Optional[datetime] = Field(None, alias="createdBefore")

    model_config = {
        "populate_by_name": True,
        "json_encoders": {datetime: lambda v: v.isoformat() if v else None},
    }

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to camelCase dict for API calls."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


__all__ = ["DocumentQuery"]
