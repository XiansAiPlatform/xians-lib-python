"""DocumentOptions model. Matches C# Xians.Lib.Agents.Documents.Models.DocumentOptions."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentOptions(BaseModel):
    """Options for document storage operations.

    Matches C# DocumentOptions. Sensible defaults:
    - UseKeyAsIdentifier = True (Type+Key becomes the unique identifier)
    - Overwrite = True (saving same Type+Key updates the existing document)
    - TtlMinutes = None (no expiration)
    """

    ttl_minutes: Optional[int] = Field(None, alias="ttlMinutes")
    overwrite: bool = Field(True, alias="overwrite")
    use_key_as_identifier: bool = Field(True, alias="useKeyAsIdentifier")

    model_config = {"populate_by_name": True}

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to camelCase dict for API calls."""
        return self.model_dump(by_alias=True, exclude_none=True)


__all__ = ["DocumentOptions"]
