"""High-level document storage operations for an agent.

Matches C# DocumentCollection. Provides agent-scoped CRUD operations
with automatic multi-level scoping (agent, context, tenant).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ...agents.core.xians_context import XiansContext
from .document_executor import DocumentActivityExecutor
from .models.document import Document
from .models.document_options import DocumentOptions
from .models.document_query import DocumentQuery

if TYPE_CHECKING:
    from ...interfaces.v1.xians_client import XiansServerClient

logger = logging.getLogger(__name__)


class DocumentCollection:
    """Provides document storage operations for an agent.

    Documents are scoped to the agent and tenant.
    Matches C# DocumentCollection with context-aware execution.
    """

    def __init__(
        self,
        agent_name: str,
        http_client: XiansServerClient,
        tenant_id: str,
        system_scoped: bool = False,
    ) -> None:
        self._agent_name = agent_name
        self._http_client = http_client
        self._tenant_id = tenant_id
        self._system_scoped = system_scoped
        self._executor = DocumentActivityExecutor(http_client, logger)

    async def save_async(
        self,
        document: Document,
        options: Optional[DocumentOptions] = None,
    ) -> Document:
        """Save a document to the database.

        Automatically sets AgentId and workflow context fields.
        If the document has no ID, one will be generated.

        Args:
            document: The document to save.
            options: Optional storage options (TTL, overwrite, etc.).

        Returns:
            The saved document with its assigned ID.
        """
        tenant_id = self._get_tenant_id()
        self._prepare_document_for_save(document)

        logger.debug(
            "Saving document for agent '%s', tenant '%s'",
            self._agent_name,
            tenant_id,
        )
        return await self._executor.save_async(document, tenant_id, options)

    async def get_async(self, document_id: str) -> Document | None:
        """Retrieve a document by its ID.

        Returns None if the document doesn't exist or belongs to a different agent.

        Args:
            document_id: The document ID.

        Returns:
            The document if found and owned by this agent, None otherwise.
        """
        tenant_id = self._get_tenant_id()
        logger.debug(
            "Getting document '%s' for agent '%s'", document_id, self._agent_name
        )

        document = await self._executor.get_async(document_id, tenant_id)
        return self._filter_document_by_agent(document, document_id)

    async def get_by_key_async(self, doc_type: str, key: str) -> Document | None:
        """Retrieve a document by its type and key combination.

        Uses query (not /get-by-key) for consistency with C# DocumentCollection.

        Args:
            doc_type: The document type.
            key: The document key.

        Returns:
            The document if found, None otherwise.
        """
        tenant_id = self._get_tenant_id()
        logger.debug(
            "Getting document by key: Type='%s', Key='%s', Agent='%s'",
            doc_type,
            key,
            self._agent_name,
        )

        query = DocumentQuery(
            type=doc_type,
            key=key,
            agent_id=self._agent_name,
            limit=1,
        )

        if XiansContext.in_workflow_or_activity():
            query.activation_name = XiansContext.safe_id_postfix()
            query.participant_id = XiansContext.safe_participant_id()

        docs = await self._executor.query_async(query, tenant_id)
        return docs[0] if docs else None

    async def query_async(self, query: DocumentQuery) -> list[Document]:
        """Query documents based on filters.

        Automatically scopes query to the current agent. When in workflow
        context, ActivationName and ParticipantId are auto-populated.

        Args:
            query: The query parameters.

        Returns:
            A list of matching documents.
        """
        tenant_id = self._get_tenant_id()
        query.agent_id = self._agent_name

        if XiansContext.in_workflow_or_activity():
            if query.activation_name is None:
                query.activation_name = XiansContext.safe_id_postfix()
            if query.participant_id is None:
                query.participant_id = XiansContext.safe_participant_id()

        logger.debug(
            "Querying documents for agent '%s': Type='%s', Limit=%s",
            self._agent_name,
            query.type,
            query.limit,
        )
        return await self._executor.query_async(query, tenant_id)

    async def update_async(self, document: Document) -> bool:
        """Update an existing document.

        The document must have an ID.

        Args:
            document: The document to update.

        Returns:
            True if updated successfully, False if not found.
        """
        tenant_id = self._get_tenant_id()
        self._prepare_document_for_save(document)

        logger.debug(
            "Updating document '%s' for agent '%s'", document.id, self._agent_name
        )
        return await self._executor.update_async(document, tenant_id)

    async def delete_async(self, document_id: str) -> bool:
        """Delete a document by its ID.

        Verifies the document belongs to this agent before deletion.

        Args:
            document_id: The document ID to delete.

        Returns:
            True if deleted successfully, False if not found.
        """
        tenant_id = self._get_tenant_id()

        logger.debug(
            "Deleting document '%s' for agent '%s'", document_id, self._agent_name
        )

        document = await self.get_async(document_id)
        if document is None:
            logger.debug(
                "Document '%s' not found or doesn't belong to agent '%s'",
                document_id,
                self._agent_name,
            )
            return False

        return await self._executor.delete_async(document_id, tenant_id)

    async def delete_many_async(self, ids: list[str]) -> int:
        """Delete multiple documents by their IDs.

        Filters IDs to only include documents belonging to this agent.

        Args:
            ids: The document IDs to delete.

        Returns:
            The number of documents successfully deleted.
        """
        logger.debug(
            "Deleting %d documents for agent '%s'", len(ids), self._agent_name
        )

        valid_ids = await self._filter_valid_document_ids(ids)
        if not valid_ids:
            return 0

        deleted_count = 0
        for doc_id in valid_ids:
            if await self.delete_async(doc_id):
                deleted_count += 1
        return deleted_count

    async def exists_async(self, document_id: str) -> bool:
        """Check if a document exists and belongs to this agent.

        Args:
            document_id: The document ID to check.

        Returns:
            True if the document exists, False otherwise.
        """
        logger.debug(
            "Checking existence of document '%s' for agent '%s'",
            document_id,
            self._agent_name,
        )
        document = await self.get_async(document_id)
        return document is not None

    # ------------------------------------------------------------------
    # Shared business logic
    # ------------------------------------------------------------------

    def _prepare_document_for_save(self, document: Document) -> None:
        """Set agent and workflow metadata on the document before save/update."""
        document.agent_id = self._agent_name
        if XiansContext.in_workflow_or_activity():
            document.workflow_id = XiansContext.safe_workflow_id()
            document.activation_name = XiansContext.safe_id_postfix()
            document.participant_id = XiansContext.safe_participant_id()

    def _filter_document_by_agent(
        self, document: Document | None, document_id: str | None = None
    ) -> Document | None:
        """Return None if the document doesn't belong to this agent."""
        if document is None:
            return None
        if document.agent_id != self._agent_name:
            logger.warning(
                "Document %s found but belongs to different agent. Expected: '%s', Found: '%s'",
                f"'{document_id}'" if document_id else "",
                self._agent_name,
                document.agent_id,
            )
            return None
        return document

    async def _filter_valid_document_ids(self, ids: list[str]) -> list[str]:
        """Filter IDs to only those belonging to this agent."""
        valid_ids: list[str] = []
        for doc_id in ids:
            doc = await self.get_async(doc_id)
            if doc is not None:
                valid_ids.append(doc_id)

        if not valid_ids:
            logger.debug("No valid documents to delete for agent '%s'", self._agent_name)
        elif len(valid_ids) < len(ids):
            logger.warning(
                "Filtered out %d documents that don't belong to agent '%s'",
                len(ids) - len(valid_ids),
                self._agent_name,
            )
        return valid_ids

    def _get_tenant_id(self) -> str:
        """Resolve tenant ID based on agent scope.

        Non-system-scoped agents use the configured tenant ID.
        System-scoped agents must resolve tenant from workflow context.
        """
        if not self._system_scoped:
            if not self._tenant_id:
                raise RuntimeError(
                    "Tenant ID cannot be determined. XiansOptions must be "
                    "properly configured with an API key."
                )
            return self._tenant_id

        tenant_id = XiansContext.get_tenant_id()
        if not tenant_id:
            raise RuntimeError(
                "Documents API for system-scoped agents can only be used "
                "within a workflow or activity context. The tenant ID is "
                "extracted from the workflow ID at runtime."
            )
        return tenant_id


__all__ = ["DocumentCollection"]
