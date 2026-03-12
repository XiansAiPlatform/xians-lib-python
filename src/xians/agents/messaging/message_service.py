"""MessageService - HTTP client for messaging operations. Matches C# MessageService."""

import asyncio
import logging
from typing import Any, Optional

import httpx

from ...temporal_workflows.v1.models import (
    SendMessageRequest,
    SendHandoffRequest,
    DbMessage,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_MAX_RETRIES = 3
RATE_LIMIT_DEFAULT_WAIT = 60


class MessageService:
    """HTTP client for messaging operations. Matches C# MessageService.

    All requests include X-Tenant-Id header.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self._client = http_client

    async def send_async(self, request: SendMessageRequest) -> None:
        """Send an outbound message.
        POST /api/agent/conversation/outbound/{type}

        Retries on 429 (rate limit).
        """
        msg_type = (request.type or "chat").lower()
        endpoint = f"/api/agent/conversation/outbound/{msg_type}"

        payload: dict[str, Any] = {
            "participantId": request.participant_id or "",
            "workflowId": request.workflow_id or "",
            "workflowType": request.workflow_type or "",
            "requestId": request.request_id or "",
            "scope": request.scope or "",
            "text": request.text or "",
            "data": request.data,
            "authorization": request.authorization,
            "threadId": request.thread_id or "",
            "origin": request.origin,
            "hint": request.hint or "",
            "taskId": request.task_id,
        }

        headers: dict[str, str] = {}
        if request.tenant_id:
            headers["X-Tenant-Id"] = request.tenant_id

        # Debug: log request/response for outbound chat to troubleshoot Unknown Participant
        logger.info(
            "[DEBUG] Outbound message request body endpoint=%s participantId=%r workflowId=%s type=%s payload=%s",
            endpoint,
            request.participant_id,
            request.workflow_id,
            request.type,
            payload,
        )
        logger.debug("[DEBUG] Full outbound payload: %s", payload)

        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            response = await self._client.post(endpoint, json=payload, headers=headers)

            # Debug: log response for outbound request (in message so it appears with default formatters)
            try:
                response_body = response.text
                if response.headers.get("content-type", "").startswith("application/json") and response_body:
                    response_body = response.json()
            except Exception:
                response_body = response.text
            logger.info(
                "[DEBUG] Outbound message response endpoint=%s status_code=%s participantId=%r response_body=%s",
                endpoint,
                response.status_code,
                request.participant_id,
                response_body,
            )

            if response.status_code == 429:
                retry_after = self._get_retry_after(response)
                logger.warning(
                    f"Rate limited. Retrying after {retry_after}s (attempt {attempt + 1})"
                )
                await asyncio.sleep(retry_after)
                continue

            response.raise_for_status()
            return

        logger.error(f"Failed to send message after {RATE_LIMIT_MAX_RETRIES} retries")

    async def get_history_async(
        self,
        workflow_id: str,
        workflow_type: str,
        participant_id: str,
        scope: str,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> list[DbMessage]:
        """Get conversation history. GET /api/agent/conversation/history"""
        params: dict[str, Any] = {
            "workflowId": workflow_id,
            "workflowType": workflow_type,
            "participantId": participant_id,
            "scope": scope,
            "page": page,
            "pageSize": page_size,
        }
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id

        response = await self._client.get(
            "/api/agent/conversation/history",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        return [
            DbMessage(
                id=msg.get("id", ""),
                thread_id=msg.get("threadId", ""),
                created_at=msg.get("createdAt", ""),
                updated_at=msg.get("updatedAt", ""),
                direction=msg.get("direction", ""),
                text=msg.get("text", ""),
                status=msg.get("status", ""),
                data=msg.get("data"),
                participant_id=msg.get("participantId", ""),
                workflow_id=msg.get("workflowId", ""),
                workflow_type=msg.get("workflowType", ""),
                request_id=msg.get("requestId", ""),
            )
            for msg in (data if isinstance(data, list) else [])
        ]

    async def get_last_task_id_async(
        self,
        workflow_id: str,
        participant_id: str,
        scope: str,
        tenant_id: str,
    ) -> Optional[str]:
        """Get last task ID. GET /api/agent/conversation/last-task-id"""
        params: dict[str, Any] = {
            "workflowId": workflow_id,
            "participantId": participant_id,
            "scope": scope,
        }
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id

        response = await self._client.get(
            "/api/agent/conversation/last-task-id",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        result = response.text.strip().strip('"')
        return result if result else None

    async def send_handoff_async(self, request: SendHandoffRequest) -> Optional[str]:
        """Send handoff request. POST /api/agent/conversation/outbound/handoff"""
        payload: dict[str, Any] = {
            "targetWorkflowId": request.target_workflow_id,
            "targetWorkflowType": request.target_workflow_type,
            "sourceAgent": request.source_agent,
            "sourceWorkflowType": request.source_workflow_type,
            "sourceWorkflowId": request.source_workflow_id,
            "threadId": request.thread_id,
            "participantId": request.participant_id,
            "authorization": request.authorization,
            "text": request.text,
            "data": request.data,
        }
        headers: dict[str, str] = {}
        if request.tenant_id:
            headers["X-Tenant-Id"] = request.tenant_id

        response = await self._client.post(
            "/api/agent/conversation/outbound/handoff",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        result = response.text.strip().strip('"')
        return result if result else None

    @staticmethod
    def _get_retry_after(response: httpx.Response) -> float:
        """Extract retry-after from response."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        try:
            body = response.json()
            if isinstance(body, dict) and "retryAfter" in body:
                return float(body["retryAfter"])
        except Exception:
            pass

        return RATE_LIMIT_DEFAULT_WAIT
