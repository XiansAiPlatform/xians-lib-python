"""Xians Server HTTP client implementation for SDK v1.

Aligned with C# HttpClientService: certificate-based auth, agent definition upload,
workflow definition hash check, and all conversation/knowledge/document endpoints.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ...exceptions.v1.errors import XiansServerError
from ...models.v1.configs import XiansServerConfig
from ...models.v1.server_contracts import (
    ChatOrDataRequest,
    FlowDefinitionRequest,
    HandoffRequest,
    UsageReportRequest,
)

logger = logging.getLogger(__name__)


class XiansServerClient:
    """Async HTTP client for Xians Server integration.

    Auth header matches C# behavior:
    - Decode PFX -> export public cert DER -> Base64 -> Bearer token
    - X-Tenant-Id header on all /api/agent/ requests
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

        headers: dict[str, str] = {"Content-Type": "application/json"}

        if config.api_key:
            try:
                from ...utils.v1.certificate import export_public_cert_base64
                public_cert_b64 = export_public_cert_base64(config.api_key)
                headers["Authorization"] = f"Bearer {public_cert_b64}"
            except Exception:
                headers["Authorization"] = f"Bearer {config.api_key}"

        if config.tenant_id:
            headers["X-Tenant-Id"] = config.tenant_id

        self._client = httpx.AsyncClient(
            base_url=config.server_url.rstrip("/"),
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
            headers=headers,
            transport=transport,
        )

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
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
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache file: {e}")
        return {}

    def _save_cache(self) -> None:
        try:
            with open(self._cache_file, "w") as f:
                json.dump(self._uploaded_hashes, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache file: {e}")

    # --- Settings ---

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_temporal_settings(self) -> dict[str, Any]:
        """GET /api/agent/settings/flowserver"""
        try:
            response = await self._request("GET", "/api/agent/settings/flowserver")
            data = response.json()
            logger.info("Successfully fetched Temporal settings from Xians Server")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                error_msg = (
                    "Authentication failed (401 Unauthorized). "
                    "Please verify that your server credentials are valid."
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

    # --- Agent Definition Upload (NEW - C# parity) ---

    async def upload_agent_definition(
        self,
        agent_name: str,
        system_scoped: bool,
        description: Optional[str] = None,
        summary: Optional[str] = None,
        version: Optional[str] = None,
        author: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """POST /api/agent/definitions/agent

        Matches C# WorkflowDefinitionUploader.UploadAgentAsync()
        """
        payload: dict[str, Any] = {
            "agentName": agent_name,
            "systemScoped": system_scoped,
        }
        if description:
            payload["description"] = description
        if summary:
            payload["summary"] = summary
        if version:
            payload["version"] = version
        if author:
            payload["author"] = author
        if category:
            payload["category"] = category

        response = await self._request(
            "POST",
            "/api/agent/definitions/agent",
            json=payload,
        )
        logger.info(f"Uploaded agent definition: {agent_name}")

    # --- Workflow Definition Hash Check (NEW - C# parity) ---

    async def check_definition_hash(
        self,
        workflow_type: str,
        system_scoped: bool,
        hash_value: str,
    ) -> bool:
        """GET /api/agent/definitions/check?workflowType=...&systemScoped=...&hash=...

        Returns True if definition is current (200), False if outdated/missing (404).
        """
        params = {
            "workflowType": workflow_type,
            "systemScoped": str(system_scoped).lower(),
            "hash": hash_value,
        }
        try:
            response = await self._client.get(
                "/api/agent/definitions/check",
                params=params,
            )
            return response.status_code == 200
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    # --- Flow Definition Upload ---

    async def upload_flow_definition(
        self,
        definition: FlowDefinitionRequest | dict,
    ) -> dict[str, Any]:
        """POST /api/agent/definitions"""
        if isinstance(definition, dict):
            payload = definition
        else:
            payload = definition.model_dump(by_alias=True, exclude_none=True)

        logger.debug(f"Uploading flow definition: {payload.get('workflowType', 'unknown')}")

        response = await self._request(
            "POST",
            "/api/agent/definitions",
            json=payload,
        )
        result = response.json()
        logger.info(f"Successfully uploaded flow definition: {payload.get('workflowType')}")
        return result

    # --- Conversation Endpoints ---

    async def send_outbound_chat(self, request: ChatOrDataRequest) -> dict[str, Any]:
        payload = request.model_dump(by_alias=True, exclude_none=True)
        logger.info(
            "[DEBUG] XiansServerClient send_outbound_chat request body",
            extra={"participantId": payload.get("participantId"), "workflowId": payload.get("workflowId"), "url": "/api/agent/conversation/outbound/chat"},
        )
        logger.debug("[DEBUG] Full send_outbound_chat payload: %s", payload)
        response = await self._request("POST", "/api/agent/conversation/outbound/chat", json=payload)
        response_json = response.json()
        logger.info(
            "[DEBUG] XiansServerClient send_outbound_chat response",
            extra={"status_code": response.status_code, "response_body": response_json},
        )
        return response_json

    async def send_outbound_data(self, request: ChatOrDataRequest) -> dict[str, Any]:
        payload = request.model_dump(by_alias=True, exclude_none=True)
        response = await self._request("POST", "/api/agent/conversation/outbound/data", json=payload)
        return response.json()

    async def send_outbound_webhook(self, request: ChatOrDataRequest) -> dict[str, Any]:
        payload = request.model_dump(by_alias=True, exclude_none=True)
        response = await self._request("POST", "/api/agent/conversation/outbound/webhook", json=payload)
        return response.json()

    async def send_handoff(self, request: HandoffRequest) -> dict[str, Any]:
        payload = request.model_dump(by_alias=True, exclude_none=True)
        response = await self._request("POST", "/api/agent/conversation/outbound/handoff", json=payload)
        return response.json()

    async def report_usage(self, request: UsageReportRequest) -> None:
        """Report usage (legacy format: promptTokens, completionTokens, etc.).

        The server returns HTTP 202 Accepted with an empty body on success.
        """
        payload = request.model_dump(by_alias=True, exclude_none=True)
        await self._request("POST", "/api/agent/usage/report", json=payload)

    async def report_metrics_usage(self, payload: dict[str, Any]) -> None:
        """Report flexible metrics (category/type/value/unit format).

        Matches C# MetricsService.ReportAsync. Accepts serialized UsageReportRequest
        from agents.metrics.models (tenantId, participantId, metrics array, etc.).

        The server returns HTTP 202 Accepted with an empty body on success.
        """
        await self._request("POST", "/api/agent/usage/report", json=payload)

    # --- Workflow Logs ---

    async def upload_agent_logs(self, payload: list[dict[str, Any]]) -> None:
        """Upload workflow logs.

        Endpoint:
            POST /api/agent/logs
        Body:
            JSON array of log request objects.
        """
        await self._request("POST", "/api/agent/logs", json=payload)

    # --- Knowledge Endpoints (aligned with C# ServerKnowledgeProvider) ---

    async def get_latest_knowledge(
        self,
        name: str,
        agent: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /api/agent/knowledge/latest (tenant-scoped, progressive fallback)"""
        params: dict[str, str] = {"name": name, "agent": agent}
        if activation_name:
            params["activationName"] = activation_name
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        response = await self._request("GET", "/api/agent/knowledge/latest", params=params, headers=headers)
        return response.json()

    async def get_system_knowledge(
        self,
        name: str,
        agent: str,
        activation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /api/agent/knowledge/latest/system (system-scoped, no tenant)"""
        params: dict[str, str] = {"name": name, "agent": agent}
        if activation_name:
            params["activationName"] = activation_name
        response = await self._request("GET", "/api/agent/knowledge/latest/system", params=params)
        return response.json()

    async def list_knowledge(
        self,
        agent: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /api/agent/knowledge/list"""
        params: dict[str, str] = {"agent": agent}
        if activation_name:
            params["activationName"] = activation_name
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        response = await self._request("GET", "/api/agent/knowledge/list", params=params, headers=headers)
        return response.json()

    async def create_knowledge(
        self,
        name: str,
        agent: str,
        content: str,
        type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        system_scoped: bool = False,
        activation_name: Optional[str] = None,
        description: Optional[str] = None,
        visible: bool = True,
    ) -> dict[str, Any]:
        """POST /api/agent/knowledge (create or update)"""
        payload: dict[str, Any] = {
            "name": name,
            "agent": agent,
            "content": content,
            "systemScoped": system_scoped,
            "visible": visible,
        }
        if type is not None:
            payload["type"] = type
        if tenant_id is not None:
            payload["tenantId"] = tenant_id
        if description is not None:
            payload["description"] = description
        params: dict[str, str] = {}
        if activation_name:
            params["activationName"] = activation_name
        response = await self._request(
            "POST", "/api/agent/knowledge", json=payload,
            params=params if params else None,
        )
        return response.json()

    async def delete_knowledge(
        self,
        name: str,
        agent: str,
        tenant_id: Optional[str] = None,
        activation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """DELETE /api/agent/knowledge"""
        params: dict[str, str] = {"name": name, "agent": agent}
        if activation_name:
            params["activationName"] = activation_name
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        response = await self._request("DELETE", "/api/agent/knowledge", params=params, headers=headers)
        return response.json()

    # --- Document Endpoints ---

    async def save_document(self, document: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"document": document}
        if options is not None:
            payload["options"] = options
        response = await self._request("POST", "/api/agent/documents/save", json=payload)
        return response.json()

    async def update_document(self, document: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"document": document}
        if options is not None:
            payload["options"] = options
        response = await self._request("POST", "/api/agent/documents/update", json=payload)
        return response.json()

    async def get_document(self, id: str) -> dict[str, Any]:
        response = await self._request("POST", "/api/agent/documents/get", json={"id": id})
        return response.json()

    async def get_document_by_key(self, type: str, key: str) -> dict[str, Any]:
        response = await self._request("POST", "/api/agent/documents/get-by-key", json={"type": type, "key": key})
        return response.json()

    async def query_documents(self, query: dict[str, Any], content_type: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if content_type is not None:
            payload["contentType"] = content_type
        response = await self._request("POST", "/api/agent/documents/query", json=payload)
        return response.json()

    async def delete_document(self, id: str) -> dict[str, Any]:
        response = await self._request("POST", "/api/agent/documents/delete", json={"id": id})
        return response.json()

    async def delete_many_documents(self, ids: list[str]) -> dict[str, Any]:
        response = await self._request("POST", "/api/agent/documents/delete-many", json={"ids": ids})
        return response.json()

    async def document_exists(self, id: str) -> dict[str, Any]:
        response = await self._request("POST", "/api/agent/documents/exists", json={"id": id})
        return response.json()

    # --- Lifecycle ---

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "XiansServerClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


__all__ = ["XiansServerClient"]
