"""Xians Server HTTP client implementation for SDK v1."""

import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ...exceptions.v1.errors import XiansServerError
from ...models.v1.configs import XiansServerConfig
from ...models.v1.entities import AgentDefinition, WorkflowDefinition
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
        """Make an HTTP request with retry handling."""
        response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

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

    async def upload_agent_definition(self, definition: AgentDefinition) -> str:
        """
        Upload agent definition to Xians Server (idempotent).
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
            response.raise_for_status()
            result = response.json()
            agent_key = result.get("agent_key", definition.name)

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

    async def upload_workflow_definition(
        self,
        agent_definition: AgentDefinition,
        workflow_definition: WorkflowDefinition,
    ) -> str:
        """
        Upload workflow definition to Xians Server (idempotent).

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
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            workflow_id = result.get("workflow_id", workflow_definition.name)

            self._uploaded_hashes[cache_key] = definition_hash
            self._save_cache()

            logger.info(f"Successfully uploaded workflow definition: {workflow_id}")
            return workflow_id
        except httpx.HTTPStatusError as e:
            # Enhanced error handling for 400 Bad Request
            error_msg = f"Failed to upload workflow definition: {e.response.status_code}"
            response_text = e.response.text

            if e.response.status_code == 400:
                # Log the payload keys (not full values to avoid exposing secrets)
                payload_keys = list(payload.keys())
                error_msg = (
                    f"Bad Request (400) uploading workflow definition to /api/agent/definitions. "
                    f"Server rejected the payload. "
                    f"Payload keys sent: {payload_keys}. "
                    f"Server response: {response_text}"
                )
                logger.error(error_msg)

            raise XiansServerError(
                error_msg,
                status_code=e.response.status_code,
                response_body=response_text,
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
        """
        payload = {
            "conversation_id": conversation_id,
            "message": message,
            "metadata": metadata or {},
        }

        try:
            response = await self._request(
                "POST",
                "/api/agent/conversation/outbound",
                json=payload,
            )
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
        """
        try:
            await self._request("POST", "/api/agent/usage", json=event)
            logger.debug("Successfully sent usage event")
        except httpx.HTTPStatusError as e:
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
        """
        payload = {
            "query": query,
            "top_k": top_k,
            "metadata_filter": metadata_filter or {},
        }

        try:
            response = await self._request("POST", "/api/agent/knowledge/search", json=payload)
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
        """
        try:
            response = await self._request("GET", f"/api/agent/documents/{document_id}")
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

