"""Temporal activities for message processing. Matches C# MessageActivities."""

import logging
from typing import Optional

from temporalio import activity

from .models import (
    ProcessMessageActivityRequest,
    SendMessageRequest,
    SendHandoffRequest,
    DbMessage,
)
from ...agents.messaging.user_message_context import UserMessageContext
from ...agents.messaging.webhook_context import WebhookContext, WebhookMessage
from ...agents.messaging.message_service import MessageService
from ...agents.core.xians_context import XiansContext

logger = logging.getLogger(__name__)


class MessageActivities:
    """Temporal activities for message processing. Matches C# MessageActivities."""

    def __init__(self, message_service: MessageService):
        self._message_service = message_service

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

        # Debug: log participant_id at activity start to troubleshoot Unknown Participant
        logger.info(
            "[DEBUG] ProcessAndSendMessage activity started",
            extra={
                "workflow_type": request.workflow_type,
                "workflow_id": request.workflow_id,
                "participant_id": request.participant_id,
                "message_type": message_type,
                "request_id": request.request_id,
            },
        )

        # Populate XiansContext with workflow and agent identity so that
        # XiansContext.CurrentAgent / CurrentWorkflow resolve inside handlers.
        XiansContext.set_workflow_id(request.workflow_id)
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

        try:
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
                    await handler(context)

            elif message_type == "webhook":
                webhook_msg = WebhookMessage(
                    participant_id=request.participant_id,
                    scope=request.scope,
                    name="",
                    payload=request.data,
                    authorization=request.authorization,
                    request_id=request.request_id,
                    tenant_id=request.tenant_id,
                )
                webhook_context = WebhookContext(webhook=webhook_msg)

                if metadata.webhook_handler:
                    await metadata.webhook_handler(webhook_context)

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

        except Exception as e:
            logger.error(f"Handler error: {e}")
            await self._send_error_to_user(request, str(e))
        finally:
            # Clear context to avoid leaking identity across activities
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
        # Debug: log outbound SendMessageRequest to troubleshoot participant routing
        logger.info(
            "[DEBUG] SendMessage activity executing",
            extra={
                "participant_id": request.participant_id,
                "workflow_id": request.workflow_id,
                "workflow_type": request.workflow_type,
                "type": request.type,
                "request_id": request.request_id,
            },
        )
        logger.debug("[DEBUG] Full SendMessageRequest: %s", request.__dict__ if hasattr(request, "__dict__") else str(request))
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
