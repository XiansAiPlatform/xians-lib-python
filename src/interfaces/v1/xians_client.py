"""Xians Server HTTP client implementation for SDK v1."""

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ...exceptions.v1.errors import XiansServerError
from ...models.v1.configs import XiansServerConfig
from ...models.v1.entities import AgentDefinition, WorkflowDefinition
from ...utils.v1.hashing import compute_hash

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
    ) -> None:
        """
        Initialize Xians Server client.

        Args:
            config: Server connection configuration.
            cache_dir: Optional directory for caching uploaded definition hashes.
        """
        self.config = config
        self.cache_dir = cache_dir or Path.home() / ".xians" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "uploaded_definitions.json"
        self._uploaded_hashes: dict[str, str] = self._load_cache()

        # Create httpx client
        self._client = httpx.AsyncClient(
            base_url=str(config.server_url),
            headers={"X-API-Key": config.api_key.get_secret_value()},
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
        )

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

        Returns:
            Dictionary containing Temporal host, port, namespace, etc.

        Raises:
            XiansServerError: If the request fails.
        """
        try:
            response = await self._client.get("/api/agent/settings/flowserver")
            response.raise_for_status()
            data = response.json()
            logger.info("Successfully fetched Temporal settings from Xians Server")
            return data
        except httpx.HTTPStatusError as e:
            raise XiansServerError(
                f"Failed to fetch Temporal settings: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error fetching Temporal settings: {str(e)}",
                cause=e,
            )

    async def upload_agent_definition(self, definition: AgentDefinition) -> str:
        """
        Upload agent definition to Xians Server (idempotent).

        Args:
            definition: The agent definition to upload.

        Returns:
            The agent key (identifier) assigned by the server.

        Raises:
            XiansServerError: If the upload fails.
        """
        # Compute hash for idempotency
        content = definition.model_dump_json(exclude={"hash", "agent_key"})
        definition_hash = compute_hash(content)
        definition.hash = definition_hash

        # Check if already uploaded
        cache_key = f"agent:{definition.name}"
        if cache_key in self._uploaded_hashes:
            cached_hash = self._uploaded_hashes[cache_key]
            if cached_hash == definition_hash:
                logger.debug(f"Agent '{definition.name}' already uploaded (hash: {definition_hash})")
                return definition.agent_key or definition.name

        # Upload to server
        try:
            response = await self._client.post(
                "/api/agent/definitions",
                json=definition.model_dump(mode="json"),
            )
            response.raise_for_status()
            result = response.json()
            agent_key = result.get("agent_key", definition.name)

            # Cache the uploaded hash
            self._uploaded_hashes[cache_key] = definition_hash
            self._save_cache()

            logger.info(f"Successfully uploaded agent definition: {agent_key}")
            return agent_key
        except httpx.HTTPStatusError as e:
            raise XiansServerError(
                f"Failed to upload agent definition: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error uploading agent definition: {str(e)}",
                cause=e,
            )

    async def upload_workflow_definition(self, definition: WorkflowDefinition) -> str:
        """
        Upload workflow definition to Xians Server (idempotent).

        Args:
            definition: The workflow definition to upload.

        Returns:
            The workflow identifier assigned by the server.

        Raises:
            XiansServerError: If the upload fails.
        """
        # Compute hash for idempotency
        content = definition.model_dump_json(exclude={"hash"})
        definition_hash = compute_hash(content)
        definition.hash = definition_hash

        # Check if already uploaded
        cache_key = f"workflow:{definition.agent_key}:{definition.name}"
        if cache_key in self._uploaded_hashes:
            cached_hash = self._uploaded_hashes[cache_key]
            if cached_hash == definition_hash:
                logger.debug(f"Workflow '{definition.name}' already uploaded (hash: {definition_hash})")
                return definition.name

        # Upload to server
        try:
            response = await self._client.post(
                "/api/agent/definitions/workflows",
                json=definition.model_dump(mode="json"),
            )
            response.raise_for_status()
            result = response.json()
            workflow_id = result.get("workflow_id", definition.name)

            # Cache the uploaded hash
            self._uploaded_hashes[cache_key] = definition_hash
            self._save_cache()

            logger.info(f"Successfully uploaded workflow definition: {workflow_id}")
            return workflow_id
        except httpx.HTTPStatusError as e:
            raise XiansServerError(
                f"Failed to upload workflow definition: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error uploading workflow definition: {str(e)}",
                cause=e,
            )

    async def send_outbound_message(
        self,
        conversation_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Send an outbound message to a conversation.

        Args:
            conversation_id: The conversation identifier.
            message: The message text to send.
            metadata: Optional additional metadata.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {
            "conversation_id": conversation_id,
            "message": message,
            "metadata": metadata or {},
        }

        try:
            response = await self._client.post(
                "/api/agent/conversation/outbound",
                json=payload,
            )
            response.raise_for_status()
            logger.debug(f"Successfully sent outbound message to conversation {conversation_id}")
        except httpx.HTTPStatusError as e:
            raise XiansServerError(
                f"Failed to send outbound message: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error sending outbound message: {str(e)}",
                cause=e,
            )

    async def send_usage_event(self, event: dict[str, Any]) -> None:
        """
        Send a usage event to Xians Server.

        Args:
            event: Usage event data.

        Raises:
            XiansServerError: If the request fails.
        """
        try:
            response = await self._client.post("/api/agent/usage", json=event)
            response.raise_for_status()
            logger.debug("Successfully sent usage event")
        except httpx.HTTPStatusError as e:
            # Usage events are best-effort, log but don't raise
            logger.warning(f"Failed to send usage event: {e.response.status_code}")
        except Exception as e:
            logger.warning(f"Unexpected error sending usage event: {str(e)}")

    async def fetch_knowledge(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Query knowledge base.

        Args:
            query: The search query.
            top_k: Number of results to return.
            metadata_filter: Optional metadata filters.

        Returns:
            Knowledge search results.

        Raises:
            XiansServerError: If the request fails.
        """
        payload = {
            "query": query,
            "top_k": top_k,
            "metadata_filter": metadata_filter or {},
        }

        try:
            response = await self._client.post("/api/agent/knowledge/search", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise XiansServerError(
                f"Failed to fetch knowledge: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error fetching knowledge: {str(e)}",
                cause=e,
            )

    async def fetch_document(self, document_id: str) -> dict[str, Any]:
        """
        Fetch a document by ID.

        Args:
            document_id: The document identifier.

        Returns:
            Document data.

        Raises:
            XiansServerError: If the request fails.
        """
        try:
            response = await self._client.get(f"/api/agent/documents/{document_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise XiansServerError(
                f"Failed to fetch document: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
                cause=e,
            )
        except Exception as e:
            raise XiansServerError(
                f"Unexpected error fetching document: {str(e)}",
                cause=e,
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

