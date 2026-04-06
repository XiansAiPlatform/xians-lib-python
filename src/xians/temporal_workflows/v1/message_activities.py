"""Temporal activities for message processing. Matches C# MessageActivities."""

import json
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
from .message_activity_workflow_logging import (
    setup_message_activity_context,
    teardown_message_activity_context,
    try_create_workflow_log_emitter,
)
from ...agents.messaging.user_message_context import UserMessageContext
from ...agents.messaging.webhook_context import WebhookContext, WebhookMessage
from ...agents.messaging.message_service import MessageService
from ...agents.workflow_logs import WorkflowLogEmitter, WorkflowLogService, XiansLogger

logger = XiansLogger.for_name(__name__)


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
            logger.log_error(f"No handlers for workflow type: {request.workflow_type}")
            return

        message_type = request.message_type.lower()

        logger.log_debug(
            f"ProcessAndSendMessage: workflow_type={request.workflow_type} "
            f"participant_id={request.participant_id} message_type={message_type}"
        )

        log_wid, run_id, log_agent, log_participant = setup_message_activity_context(request, metadata)
        emitter = try_create_workflow_log_emitter(
            self._workflow_logs_service,
            request,
            log_workflow_id=log_wid,
            workflow_run_id=run_id,
            log_agent=log_agent,
            log_participant=log_participant,
        )

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
            logger.log_error(f"Handler error: {e}", exc=e)
            if message_type != "webhook":
                await self._send_error_to_user(request, str(e))
        finally:
            if emitter:
                await emitter.flush()
            teardown_message_activity_context()

    @activity.defn(name="SendMessage")
    async def send_message(self, request: SendMessageRequest) -> None:
        """Send an outbound message."""
        logger.log_debug(
            f"SendMessage: participant_id={request.participant_id} "
            f"workflow_id={request.workflow_id} type={request.type}"
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
        emitter: WorkflowLogEmitter | None = None,
    ) -> None:
        """Process a webhook message. Matches C# MessageActivities.ProcessWebhookAsync.

        On handler exception, sets InternalServerError response (still sends the
        webhook response back to the server).

        ``emitter`` is optional (``None`` when workflow server logging is disabled);
        upstream-only call shape is preserved via the default.
        """
        payload_data = request.data
        if payload_data is not None and not isinstance(payload_data, (dict, str)):
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
            logger.log_error(f"Webhook handler error: {e}", exc=e)
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
            logger.log_error(f"Failed to send error to user: {e}", exc=e)
