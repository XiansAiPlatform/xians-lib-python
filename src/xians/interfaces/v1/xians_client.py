"""Xians Server HTTP client implementation for SDK v1.

This client implements the canonical Xians Server REST API contracts as defined in server_contracts.py.
All endpoints follow strict payload validation and camelCase JSON serialization.
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ...exceptions.v1.errors import XiansServerError
from ...models.v1.configs import XiansServerConfig
from ...models.v1.entities import AgentDefinition, WorkflowDefinition
from ...models.v1.server_contracts import (
    ChatOrDataRequest,
    FlowDefinitionRequest,
    HandoffRequest,
    UsageReportRequest,
)
from ...utils.v1.hashing import compute_hash
from ...utils.v1.payload_builder import build_workflow_definition_payload

logger = logging.getLogger(__name__)


class XiansServerClient:
    """
    Async HTTP client for Xians Server integration.

    Provides idempotent definition uploads, settings discovery,
    and conversation/knowledge/document APIs.
    """

    def __init__(
        self,
        config: XiansServerConfig,
        cache_dir: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.cache_dir = cache_dir or Path.home() / ".xians" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "uploaded_definitions.json"
        self._uploaded_hashes: dict[str, str] = self._load_cache()

        logger.debug(
            "Initializing XiansServerClient",
            extra={"server_url": str(config.server_url)},
        )

        self._client = httpx.AsyncClient(
            base_url=str(config.server_url),
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
            event_hooks={"request": [self._inject_headers]},
            transport=transport,
        )

    async def _inject_headers(self, request: httpx.Request) -> None:
        """Inject auth and tenant headers for agent API calls."""
        if self.config.auth_mode == "bearer_cert" and self.config.bearer_cert_base64:
            request.headers.setdefault(
                "Authorization",
                f"Bearer {self.config.bearer_cert_base64.get_secret_value()}",
            )
        elif self.config.auth_mode == "x_api_key" and self.config.x_api_key:
            request.headers.setdefault("X-API-Key", self.config.x_api_key.get_secret_value())

        if "/api/agent/" in request.url.path and self.config.tenant_id:
            request.headers.setdefault("X-Tenant-Id", self.config.tenant_id)

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Request URL/path.
            **kwargs: Additional httpx.request arguments.

        Returns:
            The response object.

        Raises:
            XiansServerError: On any non-2xx response.
        """
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {method} {url}"
            raise XiansServerError(
                error_msg,
                status_code=e.response.status_code,
                response_body=e.response.text,
                method=method,
                url=url,
                cause=e,
            ) from e
        except httpx.RequestError as e:
            raise XiansServerError(
                f"Request error: {str(e)}",
                method=method,
                url=url,
                cause=e,
            ) from e

    def _load_cache(self) -> dict[str, str]:
        """Load uploaded definition hashes from cache file."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache file: {e}")
        return {}

    def _save_cache(self) -> None:
        """Save uploaded definition hashes to cache file."""
        try:
            with open(self._cache_file, "w") as f:
                json.dump(self._uploaded_hashes, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache file: {e}")

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_temporal_settings(self) -> dict[str, Any]:
        """
        Fetch Temporal connection settings from Xians Server.

        Raises:
            XiansServerError: If authentication fails or server returns an error.
        """
        try:
            response = await self._request("GET", "/api/agent/settings/flowserver")
            data = response.json()
            logger.info("Successfully fetched Temporal settings from Xians Server")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                error_msg = (
                    "Authentication failed (401 Unauthorized). "
                    "Please verify that your server credentials are valid and configured."
                )
                logger.error(error_msg)
            else:
                error_msg = f"Failed to fetch Temporal settings: {e.response.status_code}"

            raise XiansServerError(
                error_msg,
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error fetching Temporal settings: {str(e)}",
                cause=e,
            )

    async def upload_flow_definition(
        self,
        definition: FlowDefinitionRequest,
    ) -> dict[str, Any]:
        """
        Upload flow definition to Xians Server.

        Implements POST /api/agent/definitions per server contract.

        Args:
            definition: FlowDefinitionRequest with required and optional fields.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the upload fails, including 400 Bad Request details.
        """
        try:
            payload = definition.model_dump(by_alias=True, exclude_none=True)
            logger.debug(
                f"Uploading flow definition for agent='{definition.agent}', "
                f"workflowType='{definition.workflow_type}'"
            )

            response = await self._request(
                "POST",
                "/api/agent/definitions",
                json=payload,
            )
            result = response.json()
            logger.info(
                f"Successfully uploaded flow definition: agent='{definition.agent}', "
                f"workflowType='{definition.workflow_type}'"
            )
            return result
        except XiansServerError as e:
            if e.status_code == 400:
                logger.error(
                    f"Bad Request (400) uploading flow definition. "
                    f"Server rejected the payload. "
                    f"Agent: {definition.agent}, WorkflowType: {definition.workflow_type}. "
                    f"Response: {e.response_body}"
                )
            raise

    async def upload_agent_definition(self, definition: AgentDefinition) -> str:
        """
        Upload agent definition to Xians Server (idempotent).

        Deprecated: Use upload_flow_definition instead.
        This method is retained for backward compatibility.
        """
        content = definition.model_dump_json(exclude={"hash", "agent_key"})
        definition_hash = compute_hash(content)
        definition.hash = definition_hash

        cache_key = f"agent:{definition.name}"
        if cache_key in self._uploaded_hashes:
            cached_hash = self._uploaded_hashes[cache_key]
            if cached_hash == definition_hash:
                logger.debug(f"Agent '{definition.name}' already uploaded (hash: {definition_hash})")
                return definition.agent_key or definition.name

        try:
            response = await self._request(
                "POST",
                "/api/agent/definitions",
                json=definition.model_dump(mode="json"),
            )
            result = response.json()
            agent_key = result.get("agent_key", definition.name)

            self._uploaded_hashes[cache_key] = definition_hash
            self._save_cache()

            logger.info(f"Successfully uploaded agent definition: {agent_key}")
            return agent_key
        except XiansServerError as e:
            logger.error(
                f"Failed to upload agent definition '{definition.name}': {e.status_code}"
            )
            raise

    async def upload_workflow_definition(
        self,
        agent_definition: AgentDefinition,
        workflow_definition: WorkflowDefinition,
    ) -> str:
        """
        Upload workflow definition to Xians Server (idempotent).

        Deprecated: Use upload_flow_definition instead.
        This method is retained for backward compatibility.

        Args:
            agent_definition: The agent definition (needed for system_scoped flag).
            workflow_definition: The workflow definition to upload.

        Returns:
            Workflow identifier from the server response.

        Raises:
            XiansServerError: If the upload fails with detailed error information.
        """
        content = workflow_definition.model_dump_json(exclude={"hash"})
        definition_hash = compute_hash(content)
        workflow_definition.hash = definition_hash

        cache_key = f"workflow:{workflow_definition.agent_key}:{workflow_definition.name}"
        if cache_key in self._uploaded_hashes:
            cached_hash = self._uploaded_hashes[cache_key]
            if cached_hash == definition_hash:
                logger.debug(
                    f"Workflow '{workflow_definition.name}' already uploaded (hash: {definition_hash})"
                )
                return workflow_definition.name

        # Build camelCase payload for server
        payload = build_workflow_definition_payload(agent_definition, workflow_definition)

        try:
            response = await self._request(
                "POST",
                "/api/agent/definitions",
                json=payload,
            )
            result = response.json()
            workflow_id = result.get("workflow_id", workflow_definition.name)

            self._uploaded_hashes[cache_key] = definition_hash
            self._save_cache()

            logger.info(f"Successfully uploaded workflow definition: {workflow_id}")
            return workflow_id
        except XiansServerError as e:
            if e.status_code == 400:
                logger.error(
                    f"Bad Request (400) uploading workflow definition. "
                    f"Server rejected the payload for workflow '{workflow_definition.name}'. "
                    f"Response: {e.response_body}"
                )
            raise

    # ========== Conversation Outbound Endpoints (B2) ==========

    async def send_outbound_chat(self, request: ChatOrDataRequest) -> dict[str, Any]:
        """
        Send outbound chat message to participant.

        Implements POST /api/agent/conversation/outbound/chat per server contract.

        Args:
            request: ChatOrDataRequest with participantId and optional fields.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = request.model_dump(by_alias=True, exclude_none=True)
        logger.debug(f"Sending outbound chat to participant: {request.participant_id}")

        response = await self._request(
            "POST",
            "/api/agent/conversation/outbound/chat",
            json=payload,
        )
        return response.json()

    async def send_outbound_data(self, request: ChatOrDataRequest) -> dict[str, Any]:
        """
        Send outbound data to participant.

        Implements POST /api/agent/conversation/outbound/data per server contract.

        Args:
            request: ChatOrDataRequest with participantId and optional fields.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = request.model_dump(by_alias=True, exclude_none=True)
        logger.debug(f"Sending outbound data to participant: {request.participant_id}")

        response = await self._request(
            "POST",
            "/api/agent/conversation/outbound/data",
            json=payload,
        )
        return response.json()

    async def send_outbound_webhook(self, request: ChatOrDataRequest) -> dict[str, Any]:
        """
        Send outbound webhook to participant.

        Implements POST /api/agent/conversation/outbound/webhook per server contract.

        Args:
            request: ChatOrDataRequest with participantId and optional fields.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = request.model_dump(by_alias=True, exclude_none=True)
        logger.debug(f"Sending outbound webhook to participant: {request.participant_id}")

        response = await self._request(
            "POST",
            "/api/agent/conversation/outbound/webhook",
            json=payload,
        )
        return response.json()

    async def send_handoff(self, request: HandoffRequest) -> dict[str, Any]:
        """
        Send handoff to target agent/human.

        Implements POST /api/agent/conversation/outbound/handoff per server contract.

        Args:
            request: HandoffRequest with participantId, target, and optional fields.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = request.model_dump(by_alias=True, exclude_none=True)
        logger.debug(
            f"Sending handoff from participant {request.participant_id} to {request.target}"
        )

        response = await self._request(
            "POST",
            "/api/agent/conversation/outbound/handoff",
            json=payload,
        )
        return response.json()

    # Legacy method for backward compatibility
    async def send_outbound_message(
        self,
        conversation_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Send an outbound message to a conversation (legacy).

        Deprecated: Use send_outbound_chat instead.
        """
        request = ChatOrDataRequest(
            participant_id=conversation_id,
            text=message,
            data=metadata,
        )
        await self.send_outbound_chat(request)
        logger.debug(f"Successfully sent outbound message to conversation {conversation_id}")

    # ========== Usage Reporting Endpoint (B3) ==========

    async def report_usage(self, request: UsageReportRequest) -> dict[str, Any]:
        """
        Report usage/token consumption to Xians Server.

        Implements POST /api/agent/usage/report per server contract.

        Args:
            request: UsageReportRequest with token counts and optional metadata.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails or validation fails.
        """
        # Validate that at least one counter is > 0
        if (
            request.prompt_tokens == 0
            and request.completion_tokens == 0
            and request.total_tokens == 0
            and request.message_count == 0
        ):
            logger.warning(
                "Usage report with all zero counts submitted. "
                "At least one counter should be > 0."
            )

        payload = request.model_dump(by_alias=True, exclude_none=True)
        logger.debug(
            f"Reporting usage: promptTokens={request.prompt_tokens}, "
            f"completionTokens={request.completion_tokens}, "
            f"messageCount={request.message_count}"
        )

        response = await self._request(
            "POST",
            "/api/agent/usage/report",
            json=payload,
        )
        return response.json()

    # Legacy method for backward compatibility
    async def send_usage_event(self, event: dict[str, Any]) -> None:
        """
        Send a usage event to Xians Server (legacy).

        Deprecated: Use report_usage with UsageReportRequest instead.
        """
        try:
            await self._request("POST", "/api/agent/usage", json=event)
            logger.debug("Successfully sent usage event (legacy endpoint)")
        except XiansServerError:
            logger.warning("Failed to send usage event to legacy endpoint /api/agent/usage")
            # Do not re-raise for backward compatibility

    # ========== Knowledge Endpoints (B4) ==========

    async def get_latest_knowledge(self, name: str, agent: str) -> dict[str, Any]:
        """
        Get latest knowledge by name and agent.

        Implements GET /api/agent/knowledge/latest per server contract.

        Args:
            name: Knowledge name (required).
            agent: Agent identifier (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        logger.debug(f"Fetching latest knowledge: name={name}, agent={agent}")

        response = await self._request(
            "GET",
            "/api/agent/knowledge/latest",
            params={"name": name, "agent": agent},
        )
        return response.json()

    async def list_knowledge(self, agent: str) -> dict[str, Any]:
        """
        List all knowledge for an agent.

        Implements GET /api/agent/knowledge/list per server contract.

        Args:
            agent: Agent identifier (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        logger.debug(f"Listing knowledge for agent: {agent}")

        response = await self._request(
            "GET",
            "/api/agent/knowledge/list",
            params={"agent": agent},
        )
        return response.json()

    async def create_knowledge(
        self,
        name: str,
        agent: str,
        type: str,
        content: str,
    ) -> dict[str, Any]:
        """
        Create new knowledge.

        Implements POST /api/agent/knowledge per server contract.

        Args:
            name: Knowledge name (required).
            agent: Agent identifier (required).
            type: Knowledge type (required).
            content: Knowledge content (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {
            "name": name,
            "agent": agent,
            "type": type,
            "content": content,
        }
        logger.debug(f"Creating knowledge: name={name}, agent={agent}, type={type}")

        response = await self._request(
            "POST",
            "/api/agent/knowledge",
            json=payload,
        )
        return response.json()

    async def delete_knowledge(self, name: str, agent: str) -> dict[str, Any]:
        """
        Delete knowledge by name and agent.

        Implements DELETE /api/agent/knowledge per server contract.

        Args:
            name: Knowledge name (required).
            agent: Agent identifier (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        logger.debug(f"Deleting knowledge: name={name}, agent={agent}")

        response = await self._request(
            "DELETE",
            "/api/agent/knowledge",
            params={"name": name, "agent": agent},
        )
        return response.json()

    # Legacy method for backward compatibility
    async def fetch_knowledge(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Query knowledge base (legacy).

        Deprecated: Use list_knowledge or get_latest_knowledge instead.
        This endpoint (/api/agent/knowledge/search) does not exist on the server.
        """
        logger.warning(
            "fetch_knowledge is deprecated and uses non-existent /api/agent/knowledge/search endpoint. "
            "Use list_knowledge or get_latest_knowledge instead."
        )
        raise XiansServerError(
            "Knowledge search endpoint not supported. Use list_knowledge or get_latest_knowledge.",
        )

    # ========== Document Endpoints (B5) ==========

    async def save_document(
        self,
        document: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Save a document.

        Implements POST /api/agent/documents/save per server contract.

        Args:
            document: Document data (required).
            options: Optional save options.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {
            "document": document,
        }
        if options is not None:
            payload["options"] = options

        logger.debug("Saving document")

        response = await self._request(
            "POST",
            "/api/agent/documents/save",
            json=payload,
        )
        return response.json()

    async def update_document(
        self,
        document: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Update a document.

        Implements POST /api/agent/documents/update per server contract.

        Args:
            document: Document data with id (required).
            options: Optional update options.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {
            "document": document,
        }
        if options is not None:
            payload["options"] = options

        logger.debug("Updating document")

        response = await self._request(
            "POST",
            "/api/agent/documents/update",
            json=payload,
        )
        return response.json()

    async def get_document(self, id: str) -> dict[str, Any]:
        """
        Get document by ID.

        Implements POST /api/agent/documents/get per server contract.

        Args:
            id: Document ID (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {"id": id}
        logger.debug(f"Getting document: id={id}")

        response = await self._request(
            "POST",
            "/api/agent/documents/get",
            json=payload,
        )
        return response.json()

    async def get_document_by_key(self, type: str, key: str) -> dict[str, Any]:
        """
        Get document by type and key.

        Implements POST /api/agent/documents/get-by-key per server contract.

        Args:
            type: Document type (required).
            key: Document key (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {
            "type": type,
            "key": key,
        }
        logger.debug(f"Getting document by key: type={type}, key={key}")

        response = await self._request(
            "POST",
            "/api/agent/documents/get-by-key",
            json=payload,
        )
        return response.json()

    async def query_documents(
        self,
        query: dict[str, Any],
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Query documents.

        Implements POST /api/agent/documents/query per server contract.

        Args:
            query: Query object (required).
            content_type: Optional content type filter.

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {"query": query}
        if content_type is not None:
            payload["contentType"] = content_type

        logger.debug("Querying documents")

        response = await self._request(
            "POST",
            "/api/agent/documents/query",
            json=payload,
        )
        return response.json()

    async def delete_document(self, id: str) -> dict[str, Any]:
        """
        Delete document by ID.

        Implements POST /api/agent/documents/delete per server contract.

        Args:
            id: Document ID (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {"id": id}
        logger.debug(f"Deleting document: id={id}")

        response = await self._request(
            "POST",
            "/api/agent/documents/delete",
            json=payload,
        )
        return response.json()

    async def delete_many_documents(self, ids: list[str]) -> dict[str, Any]:
        """
        Delete multiple documents by IDs.

        Implements POST /api/agent/documents/delete-many per server contract.

        Args:
            ids: List of document IDs (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {"ids": ids}
        logger.debug(f"Deleting {len(ids)} documents")

        response = await self._request(
            "POST",
            "/api/agent/documents/delete-many",
            json=payload,
        )
        return response.json()

    async def document_exists(self, id: str) -> dict[str, Any]:
        """
        Check if a document exists.

        Implements POST /api/agent/documents/exists per server contract.

        Args:
            id: Document ID (required).

        Returns:
            Server response as dict.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {"id": id}
        logger.debug(f"Checking if document exists: id={id}")

        response = await self._request(
            "POST",
            "/api/agent/documents/exists",
            json=payload,
        )
        return response.json()

    # Legacy method for backward compatibility
    async def fetch_document(self, document_id: str) -> dict[str, Any]:
        """
        Fetch a document by ID (legacy).

        Deprecated: Use get_document instead.
        This endpoint (GET /api/agent/documents/{id}) does not exist on the server.
        """
        logger.warning(
            "fetch_document uses non-existent GET /api/agent/documents/{id} endpoint. "
            "Use get_document instead."
        )
        raise XiansServerError(
            "GET /api/agent/documents/{id} endpoint not supported. Use get_document (POST) instead.",
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "XiansServerClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


__all__ = ["XiansServerClient"]

