"""Temporal activities for document storage operations.

Matches C# DocumentActivities. Automatically registered with all workflows.
Activities perform non-deterministic HTTP operations on behalf of workflows.
"""

from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from .document_service import DocumentService
from .models.document import Document
from .models.document_options import DocumentOptions
from .models.document_query import DocumentQuery

logger = logging.getLogger(__name__)


class DocumentActivities:
    """Temporal activities for document CRUD operations.

    Matches C# DocumentActivities. Wraps DocumentService so workflows
    can perform document operations via activities (deterministic from
    the workflow's perspective).
    """

    def __init__(self, http_client: object) -> None:
        self._http_client = http_client
        self._logger = logging.getLogger(f"{__name__}.DocumentActivities")

    def _create_service(self) -> DocumentService:
        return DocumentService(self._http_client, self._logger)

    @activity.defn(name="SaveDocument")
    async def save_document(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        """Save a document. Receives and returns serialized dicts for Temporal compatibility."""
        activity.logger.debug(
            "SaveDocument activity started: tenant_id=%s",
            request_payload.get("tenantId"),
        )

        document = Document.from_api_dict(request_payload.get("document", {}))
        tenant_id = request_payload.get("tenantId", "")
        options_data = request_payload.get("options")
        options = DocumentOptions.model_validate(options_data) if options_data else None

        service = self._create_service()
        result = await service.save_async(document, tenant_id, options)
        return result.to_api_dict()

    @activity.defn(name="GetDocument")
    async def get_document(self, request_payload: dict[str, Any]) -> dict[str, Any] | None:
        """Get a document by ID."""
        document_id = request_payload.get("id", "")
        tenant_id = request_payload.get("tenantId", "")

        service = self._create_service()
        result = await service.get_async(document_id, tenant_id)
        return result.to_api_dict() if result else None

    @activity.defn(name="QueryDocuments")
    async def query_documents(self, request_payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Query documents."""
        query_data = request_payload.get("query", {})
        tenant_id = request_payload.get("tenantId", "")

        query = DocumentQuery.model_validate(query_data)
        service = self._create_service()
        results = await service.query_async(query, tenant_id)
        return [doc.to_api_dict() for doc in results]

    @activity.defn(name="UpdateDocument")
    async def update_document(self, request_payload: dict[str, Any]) -> bool:
        """Update a document."""
        document = Document.from_api_dict(request_payload.get("document", {}))
        tenant_id = request_payload.get("tenantId", "")

        service = self._create_service()
        return await service.update_async(document, tenant_id)

    @activity.defn(name="DeleteDocument")
    async def delete_document(self, request_payload: dict[str, Any]) -> bool:
        """Delete a document by ID."""
        document_id = request_payload.get("id", "")
        tenant_id = request_payload.get("tenantId", "")

        service = self._create_service()
        return await service.delete_async(document_id, tenant_id)


__all__ = ["DocumentActivities"]
