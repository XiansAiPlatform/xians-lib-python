"""Core service for document storage operations via HTTP.

Matches C# DocumentService. Shared by DocumentCollection and DocumentActivities
to avoid code duplication. All operations use POST with X-Tenant-Id header.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .models.document import Document
from .models.document_options import DocumentOptions
from .models.document_query import DocumentQuery

if TYPE_CHECKING:
    from ...interfaces.v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class DocumentService:
    """Core HTTP service for document CRUD operations.

    Matches C# DocumentService. Uses XiansServerClient for all HTTP calls.
    """

    def __init__(
        self,
        http_client: XiansServerClient,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        self._http_client = http_client
        self._logger = logger_instance or logger

    async def save_async(
        self,
        document: Document,
        tenant_id: str,
        options: DocumentOptions | None = None,
    ) -> Document:
        """Save a document. Matches C# DocumentService.SaveAsync."""
        if not tenant_id:
            raise ValueError("tenant_id is required")

        if options and options.use_key_as_identifier:
            missing = []
            if not document.type:
                missing.append("type")
            if not document.key:
                missing.append("key")
            if missing:
                msg = f"UseKeyAsIdentifier requires both type and key. Missing: {', '.join(missing)}"
                self._logger.error("Document save validation failed: %s", msg)
                raise ValueError(msg)

        self._logger.debug(
            "Saving document%s", f" with ID: {document.id}" if document.id else ""
        )

        doc_dict = document.to_api_dict()
        options_dict = options.to_api_dict() if options else None

        result = await self._http_client.save_document(doc_dict, options_dict)
        saved = Document.from_api_dict(result)
        self._logger.debug("Document saved successfully with ID: %s", saved.id)
        return saved

    async def get_async(self, document_id: str, tenant_id: str) -> Document | None:
        """Get a document by ID. Matches C# DocumentService.GetAsync.

        Returns None on 404 or 500 (server may return 500 for non-existent docs).
        """
        if not document_id:
            raise ValueError("document_id is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._logger.debug("Getting document with ID: %s", document_id)

        try:
            result = await self._http_client.get_document(document_id)
            doc = Document.from_api_dict(result)
            self._logger.debug("Document retrieved successfully with ID: %s", document_id)
            return doc
        except Exception as ex:
            status = getattr(ex, "status_code", None)
            if status in (404, 500):
                self._logger.debug("Document not found with ID: %s (status=%s)", document_id, status)
                return None
            raise

    async def get_by_key_async(
        self, doc_type: str, key: str, tenant_id: str
    ) -> Document | None:
        """Get a document by type+key. Matches C# DocumentService.GetByKeyAsync."""
        if not doc_type:
            raise ValueError("doc_type is required")
        if not key:
            raise ValueError("key is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._logger.debug("Getting document with Type: %s and Key: %s", doc_type, key)

        try:
            result = await self._http_client.get_document_by_key(doc_type, key)
            doc = Document.from_api_dict(result)
            self._logger.debug("Document retrieved with Type: %s, Key: %s", doc_type, key)
            return doc
        except Exception as ex:
            status = getattr(ex, "status_code", None)
            if status == 404:
                self._logger.debug("Document not found: Type=%s, Key=%s", doc_type, key)
                return None
            raise

    async def query_async(
        self, query: DocumentQuery, tenant_id: str
    ) -> list[Document]:
        """Query documents. Matches C# DocumentService.QueryAsync."""
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._logger.debug(
            "Querying documents: Type=%s, Limit=%s", query.type, query.limit
        )

        query_dict = query.to_api_dict()
        result = await self._http_client.query_documents(query_dict)

        if isinstance(result, list):
            documents = [Document.from_api_dict(d) for d in result]
        else:
            documents = []

        self._logger.debug("Query returned %d documents", len(documents))
        return documents

    async def update_async(self, document: Document, tenant_id: str) -> bool:
        """Update a document. Matches C# DocumentService.UpdateAsync.

        Returns True on success, False on 404/400.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not document.id:
            raise ValueError("Document ID is required for update")

        self._logger.debug("Updating document with ID: %s", document.id)

        document.updated_at = datetime.now(timezone.utc)

        try:
            doc_dict = document.to_api_dict()
            # Server DocumentDto requires a "content" property; exclude_none omits None.
            if "content" not in doc_dict:
                doc_dict["content"] = None
            await self._http_client.update_document(doc_dict)
            self._logger.debug("Document updated successfully with ID: %s", document.id)
            return True
        except Exception as ex:
            status = getattr(ex, "status_code", None)
            if status in (404, 400):
                self._logger.debug(
                    "Document not found for update (%s) with ID: %s", status, document.id
                )
                return False
            raise

    async def delete_async(self, document_id: str, tenant_id: str) -> bool:
        """Delete a document by ID. Matches C# DocumentService.DeleteAsync.

        Returns True on success, False on 404/400.
        """
        if not document_id:
            raise ValueError("document_id is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._logger.debug("Deleting document with ID: %s", document_id)

        try:
            await self._http_client.delete_document(document_id)
            self._logger.debug("Document deleted successfully with ID: %s", document_id)
            return True
        except Exception as ex:
            status = getattr(ex, "status_code", None)
            if status in (404, 400):
                self._logger.debug(
                    "Document not found for deletion (%s) with ID: %s", status, document_id
                )
                return False
            raise

    async def delete_many_async(
        self, ids: list[str], tenant_id: str
    ) -> int:
        """Delete multiple documents. Matches C# DocumentService.DeleteManyAsync."""
        if not ids:
            return 0
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._logger.debug("Deleting %d documents", len(ids))

        result = await self._http_client.delete_many_documents(ids)
        deleted_count = result.get("deletedCount", 0) if isinstance(result, dict) else 0

        self._logger.debug(
            "Deleted %d out of %d documents", deleted_count, len(ids)
        )
        return deleted_count

    async def exists_async(self, document_id: str, tenant_id: str) -> bool:
        """Check if a document exists. Matches C# DocumentService.ExistsAsync."""
        if not document_id:
            raise ValueError("document_id is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        self._logger.debug("Checking existence of document with ID: %s", document_id)

        result = await self._http_client.document_exists(document_id)
        exists = result.get("exists", False) if isinstance(result, dict) else False

        self._logger.debug(
            "Document %s with ID: %s",
            "exists" if exists else "does not exist",
            document_id,
        )
        return exists


__all__ = ["DocumentService"]
