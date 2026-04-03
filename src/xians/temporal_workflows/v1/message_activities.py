"""Temporal activities for message processing. Matches C# MessageActivities."""

import json
import logging
from typing import Optional

from temporalio import activity

from .models import (
    ProcessMessageActivityRequest,
    SendMessageRequest,
    SendHandoffRequest,
    WorkflowHandlerMetadata,
    DbMessage,
    WebhookResponse,
)
from ...agents.messaging.user_message_context import UserMessageContext
from ...agents.messaging.webhook_context import WebhookContext, WebhookMessage
from ...agents.messaging.message_service import MessageService
from ...agents.core.xians_context import XiansContext
from ...agents.workflow_logs import WorkflowLogEmitter, WorkflowLogService

logger = logging.getLogger(__name__)


def _temporal_workflow_id_for_logging(fallback: str | None) -> str:
    """Temporal instance id for POST /api/agent/logs ``workflowId`` (parity with .NET).

    The activity request may carry a logical/thread id ({tenant}:{workflowType}) from
    the signal payload; Temporal's execution id includes activation postfix when the
    server started the workflow that way. Auditing distinct-workflow lists key off the
    stored ``workflowId`` string, so logs must use the canonical Temporal id.
    """
    try:
        wid = (activity.info().workflow_id or "").strip()
    except Exception:
        wid = ""
    if wid:
        return wid
    return (fallback or "").strip()


def _temporal_workflow_run_id_for_logging(fallback: str | None) -> str | None:
    """Temporal run id for run-scoped Auditing / ``workflowRunId`` on ingest."""
    try:
        rid = (activity.info().workflow_run_id or "").strip()
    except Exception:
        rid = ""
    if rid:
        return rid
    fb = (fallback or "").strip()
    return fb or None


class MessageActivities:
    """Temporal activities for message processing. Matches C# MessageActivities."""

    def __init__(self, message_service: MessageService, workflow_logs_service: WorkflowLogService | None = None):
        self._message_service = message_service
        self._workflow_logs_service = workflow_logs_service

    @activity.defn(name="ProcessAndSendMessage")
    async def process_and_send_message(
        self, request: ProcessMessageActivityRequest
    ) -> None:
        """Process an inbound message by invoking the registered handler.
        Matches C# MessageActivities.ProcessAndSendMessageAsync.
        """
        from .workflows import _handlers_by_workflow_type

        metadata = _handlers_by_workflow_type.get(request.workflow_type)
        if metadata is None:
            logger.error(f"No handlers for workflow type: {request.workflow_type}")
            return

        message_type = request.message_type.lower()

        logger.debug(
            "ProcessAndSendMessage: workflow_type=%s participant_id=%s message_type=%s",
            request.workflow_type,
            request.participant_id,
            message_type,
        )

        log_workflow_id = _temporal_workflow_id_for_logging(request.workflow_id)
        workflow_run_id = _temporal_workflow_run_id_for_logging(request.workflow_run_id)

        # Populate XiansContext with workflow and agent identity so that
        # XiansContext.CurrentAgent / CurrentWorkflow resolve inside handlers.
        # Use canonical Temporal workflow id so idPostfix / activation parses match ingest.
        XiansContext.set_workflow_id(log_workflow_id)
        XiansContext.set_workflow_type(request.workflow_type)
        if request.workflow_type:
            agent_name = request.workflow_type.split(":", 1)[0]
        else:
            agent_name = None
        XiansContext.set_agent_name(agent_name)

        XiansContext.set_tenant_id(request.tenant_id)
        XiansContext.set_participant_id(request.participant_id)
        XiansContext.set_authorization(request.authorization)
        XiansContext.set_request_id(request.request_id)

        log_agent = (metadata.agent_name or "").strip() or agent_name
        log_participant = (request.participant_id or "").strip() or None

        # One emitter per activity execution; buffer is per-emitter.
        emitter: WorkflowLogEmitter | None = None
        try:
            if (
                self._workflow_logs_service
                and log_workflow_id
                and request.workflow_type
                and log_agent
            ):
                if not workflow_run_id:
                    logger.debug(
                        "WorkflowLogEmitter: workflow_run_id missing after Temporal lookup; "
                        "emitting without workflowRunId"
                    )
                emitter = WorkflowLogEmitter(
                    log_service=self._workflow_logs_service,
                    agent=log_agent,
                    workflow_type=request.workflow_type,
                    workflow_id=log_workflow_id,
                    workflow_run_id=workflow_run_id,
                    activation=XiansContext.safe_id_postfix(),
                    participant_id=log_participant,
                    tenant_id=request.tenant_id or XiansContext.safe_tenant_id(),
                )
        except Exception:
            logger.warning("Failed to initialize WorkflowLogEmitter", exc_info=True)

        try:
            if emitter:
                await emitter.emit_info(f"Workflow message received (type={message_type})")

            if message_type in ("chat", "data", "file"):
                context = UserMessageContext(
                    request=request,
                    message_service=self._message_service,
                )

                handler = {
                    "chat": metadata.chat_handler,
                    "data": metadata.data_handler,
                    "file": metadata.file_upload_handler,
                }.get(message_type)

                if handler:
                    if emitter:
                        await emitter.emit_info("Dispatching user handler")
                    await handler(context)
                    if emitter:
                        await emitter.emit_info("User handler completed successfully")

            elif message_type == "webhook":
                await self._process_webhook(request, metadata, emitter)

        except Exception as e:
            if emitter:
                await emitter.emit_error("Workflow handler failed", exc=e)
            logger.error(f"Handler error: {e}")
            if message_type != "webhook":
                await self._send_error_to_user(request, str(e))
        finally:
            if emitter:
                await emitter.flush()
            XiansContext.set_workflow_id(None)
            XiansContext.set_workflow_type(None)
            XiansContext.set_agent_name(None)
            XiansContext.set_tenant_id(None)
            XiansContext.set_participant_id(None)
            XiansContext.set_authorization(None)
            XiansContext.set_request_id(None)

    @activity.defn(name="SendMessage")
    async def send_message(self, request: SendMessageRequest) -> None:
        """Send an outbound message."""
        logger.debug(
            "SendMessage: participant_id=%s workflow_id=%s type=%s",
            request.participant_id,
            request.workflow_id,
            request.type,
        )
        await self._message_service.send_async(request)

    @activity.defn(name="GetMessageHistory")
    async def get_message_history(
        self,
        workflow_id: str,
        workflow_type: str,
        participant_id: str,
        scope: str,
        tenant_id: str,
        page: int,
        page_size: int,
    ) -> list[DbMessage]:
        """Get message history."""
        return await self._message_service.get_history_async(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            participant_id=participant_id,
            scope=scope,
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
        )

    @activity.defn(name="GetLastTaskId")
    async def get_last_task_id(
        self,
        workflow_id: str,
        participant_id: str,
        scope: str,
        tenant_id: str,
    ) -> Optional[str]:
        """Get last task ID."""
        return await self._message_service.get_last_task_id_async(
            workflow_id=workflow_id,
            participant_id=participant_id,
            scope=scope,
            tenant_id=tenant_id,
        )

    @activity.defn(name="SendHandoff")
    async def send_handoff(self, request: SendHandoffRequest) -> Optional[str]:
        """Send handoff."""
        return await self._message_service.send_handoff_async(request)

    async def _process_webhook(
        self,
        request: ProcessMessageActivityRequest,
        metadata: WorkflowHandlerMetadata,
        emitter: WorkflowLogEmitter | None,
    ) -> None:
        """Process a webhook message. Matches C# MessageActivities.ProcessWebhookAsync.

        On handler exception, sets InternalServerError response (still sends the
        webhook response back to the server).
        """
        payload_data = request.data
        if isinstance(payload_data, dict):
            pass
        elif isinstance(payload_data, str):
            pass
        elif payload_data is not None:
            payload_data = json.dumps(payload_data, default=str)

        webhook_msg = WebhookMessage(
            participant_id=request.participant_id or "",
            scope=request.scope or "",
            name="",
            payload=payload_data,
            authorization=request.authorization,
            request_id=request.request_id or "",
            tenant_id=request.tenant_id or "",
        )
        webhook_context = WebhookContext(webhook=webhook_msg)

        try:
            if metadata.webhook_handler:
                if emitter:
                    await emitter.emit_info("Dispatching webhook handler")
                await metadata.webhook_handler(webhook_context)
        except Exception as e:
            logger.error(f"Webhook handler error: {e}")
            webhook_context.response = WebhookResponse.internal_server_error(str(e))

        send_req = SendMessageRequest(
            participant_id=request.participant_id,
            workflow_id=request.workflow_id,
            workflow_type=request.workflow_type,
            request_id=request.request_id,
            scope=request.scope,
            data={
                "statusCode": webhook_context.response.status_code,
                "content": webhook_context.response.content,
                "contentType": webhook_context.response.content_type,
                "headers": webhook_context.response.headers,
            },
            text="",
            type="webhook",
            tenant_id=request.tenant_id,
        )
        await self._message_service.send_async(send_req)
        if emitter:
            await emitter.emit_info("Webhook reply sent successfully")

    async def _send_error_to_user(
        self, request: ProcessMessageActivityRequest, error_message: str
    ) -> None:
        """Send error message to user on handler failure."""
        try:
            send_req = SendMessageRequest(
                participant_id=request.participant_id,
                workflow_id=request.workflow_id,
                workflow_type=request.workflow_type,
                request_id=request.request_id,
                scope=request.scope,
                text=f"Error: {error_message}",
                type="chat",
                tenant_id=request.tenant_id,
            )
            await self._message_service.send_async(send_req)
        except Exception as e:
            logger.error(f"Failed to send error to user: {e}")
