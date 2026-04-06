"""Activity executor for document operations.

Matches C# DocumentActivityExecutor / ContextAwareActivityExecutor pattern.
Handles context-aware execution:
- In workflows: Uses DocumentActivities (deterministic, no direct HTTP)
- Outside workflows: Directly calls DocumentService (HTTP)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ...agents.core.xians_context import XiansContext
from .document_service import DocumentService
from .models.document import Document
from .models.document_options import DocumentOptions
from .models.document_query import DocumentQuery

if TYPE_CHECKING:
    from ...interfaces.v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class DocumentActivityExecutor:
    """Activity executor for document operations.

    Handles context-aware execution of document activities.
    Matches C# DocumentActivityExecutor / ContextAwareActivityExecutor pattern.
    """

    def __init__(
        self,
        http_client: XiansServerClient,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        self._http_client = http_client
        self._logger = logger_instance or logger

    def _create_service(self) -> DocumentService:
        return DocumentService(self._http_client, self._logger)

    async def save_async(
        self,
        document: Document,
        tenant_id: str,
        options: DocumentOptions | None = None,
    ) -> Document:
        """Save a document with automatic context detection."""
        if XiansContext.in_workflow():
            self._logger.debug("Executing SaveDocument via activity in workflow context")
            request: dict[str, Any] = {
                "document": document.to_api_dict(),
                "tenantId": tenant_id,
            }
            if options:
                request["options"] = options.to_api_dict()

            from datetime import timedelta

            from temporalio import workflow

            result = await workflow.execute_activity(
                "SaveDocument",
                request,
                start_to_close_timeout=timedelta(seconds=30),
            )
            return Document.from_api_dict(result)
        else:
            self._logger.debug("Executing SaveDocument via direct service call")
            service = self._create_service()
            return await service.save_async(document, tenant_id, options)

    async def get_async(
        self,
        document_id: str,
        tenant_id: str,
    ) -> Document | None:
        """Get a document by ID with automatic context detection."""
        if XiansContext.in_workflow():
            self._logger.debug("Executing GetDocument via activity in workflow context")
            request: dict[str, Any] = {
                "id": document_id,
                "tenantId": tenant_id,
            }

            from datetime import timedelta

            from temporalio import workflow

            result = await workflow.execute_activity(
                "GetDocument",
                request,
                start_to_close_timeout=timedelta(seconds=30),
            )
            return Document.from_api_dict(result) if result else None
        else:
            self._logger.debug("Executing GetDocument via direct service call")
            service = self._create_service()
            return await service.get_async(document_id, tenant_id)

    async def query_async(
        self,
        query: DocumentQuery,
        tenant_id: str,
    ) -> list[Document]:
        """Query documents with automatic context detection."""
        if XiansContext.in_workflow():
            self._logger.debug("Executing QueryDocuments via activity in workflow context")
            request: dict[str, Any] = {
                "query": query.to_api_dict(),
                "tenantId": tenant_id,
            }

            from datetime import timedelta

            from temporalio import workflow

            result = await workflow.execute_activity(
                "QueryDocuments",
                request,
                start_to_close_timeout=timedelta(seconds=30),
            )
            return [Document.from_api_dict(d) for d in (result or [])]
        else:
            self._logger.debug("Executing QueryDocuments via direct service call")
            service = self._create_service()
            return await service.query_async(query, tenant_id)

    async def update_async(
        self,
        document: Document,
        tenant_id: str,
    ) -> bool:
        """Update a document with automatic context detection."""
        if XiansContext.in_workflow():
            self._logger.debug("Executing UpdateDocument via activity in workflow context")
            request: dict[str, Any] = {
                "document": document.to_api_dict(),
                "tenantId": tenant_id,
            }

            from datetime import timedelta

            from temporalio import workflow

            return await workflow.execute_activity(
                "UpdateDocument",
                request,
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            self._logger.debug("Executing UpdateDocument via direct service call")
            service = self._create_service()
            return await service.update_async(document, tenant_id)

    async def delete_async(
        self,
        document_id: str,
        tenant_id: str,
    ) -> bool:
        """Delete a document with automatic context detection."""
        if XiansContext.in_workflow():
            self._logger.debug("Executing DeleteDocument via activity in workflow context")
            request: dict[str, Any] = {
                "id": document_id,
                "tenantId": tenant_id,
            }

            from datetime import timedelta

            from temporalio import workflow

            return await workflow.execute_activity(
                "DeleteDocument",
                request,
                start_to_close_timeout=timedelta(seconds=30),
            )
        else:
            self._logger.debug("Executing DeleteDocument via direct service call")
            service = self._create_service()
            return await service.delete_async(document_id, tenant_id)


__all__ = ["DocumentActivityExecutor"]
