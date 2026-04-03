"""Message processing pipeline. Matches C# MessageProcessor."""

import logging
from datetime import timedelta

from temporalio import workflow

from .models import (
    InboundMessage,
    ProcessMessageActivityRequest,
)
from .message_response_helper import MessageResponseHelper
from .message_validator import validate_tenant_isolation, validate_agent_name
from .tenant_context import TenantContext, WorkflowIdError

logger = logging.getLogger(__name__)

_HANDLER_HINT = {
    "chat": "OnUserChatMessage()",
    "data": "OnUserDataMessage()",
    "file": "OnFileUpload()",
    "webhook": "OnWebhook()",
}


class MessageProcessor:
    """Processes inbound messages. Matches C# MessageProcessor.

    Routes messages to the correct handler (chat, data, file, webhook)
    and executes the handler via a Temporal activity.
    """

    @staticmethod
    async def process_message(
        message: InboundMessage,
        workflow_id: str,
        workflow_type: str,
    ) -> None:
        """Process a single inbound message.

        Matches C# MessageProcessor.ProcessMessageAsync control flow:
        1. Normalize type with trim + lowercase (C# Trim + ToLowerInvariant)
        2. Heartbeat: immediate response, no handler
        3. Validate message type
        4. Look up handler
        5. Validate tenant isolation and agent name
        6. Execute message activity
        """
        payload = message.payload
        text_preview = (
            "(empty)"
            if not payload.text
            else (payload.text[:50] + "..." if len(payload.text) > 50 else payload.text)
        )

        logger.debug(
            "ProcessMessageAsync: Type=%s, Text=%s",
            payload.type,
            text_preview,
        )

        # Normalize: Trim() + ToLowerInvariant() in C#
        message_type = (payload.type or "").strip().lower()

        # Heartbeat: immediate response without invoking any handler
        # Matches C# MessageProcessor heartbeat block exactly
        if message_type == "heartbeat":
            try:
                tenant_id = TenantContext.extract_tenant_id(workflow_id)
            except (WorkflowIdError, ValueError) as ex:
                logger.error(
                    "Failed to extract tenant ID from WorkflowId for heartbeat: %s",
                    workflow_id,
                )
                # Fallback tenant: first segment if workflow_id contains ':'
                # Matches C# fallback: workflowId.Contains(':') ? workflowId.Split(':')[0] : null
                fallback_tenant = (
                    workflow_id.split(":")[0]
                    if ":" in (workflow_id or "")
                    else None
                )
                if fallback_tenant and fallback_tenant.strip():
                    try:
                        await MessageResponseHelper.send_heartbeat_unavailable_response(
                            message=message,
                            tenant_id=fallback_tenant,
                            workflow_id=workflow_id,
                            workflow_type=workflow_type,
                        )
                    except Exception as send_ex:
                        logger.error(
                            "Failed to send heartbeat unavailable response for WorkflowId=%s",
                            workflow_id,
                        )
                # No fallback tenant → no response (matches C# behavior)
                return

            logger.debug(
                "Heartbeat received: RequestId=%s, responding with available=true",
                payload.request_id,
            )
            try:
                await MessageResponseHelper.send_heartbeat_response(
                    message=message,
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    workflow_type=workflow_type,
                )
            except Exception as send_ex:
                logger.error(
                    "Failed to send heartbeat response for WorkflowId=%s",
                    workflow_id,
                )
            return

        # Only process Chat, Data, File, and Webhook type messages
        if message_type not in ("chat", "data", "file", "webhook"):
            logger.warning(
                "Skipping unsupported message type: Type=%s, RequestId=%s",
                payload.type,
                payload.request_id,
            )
            return

        from .workflows import _handlers_by_workflow_type

        metadata = _handlers_by_workflow_type.get(workflow_type)

        if metadata is None:
            await MessageResponseHelper.send_simple_message(
                message=message,
                text=f"No message handler registered for workflow type '{workflow_type}'.",
                workflow_id=workflow_id,
                workflow_type=workflow_type,
            )
            return

        handler_map = {
            "chat": metadata.chat_handler,
            "data": metadata.data_handler,
            "file": metadata.file_upload_handler,
            "webhook": metadata.webhook_handler,
        }

        if handler_map.get(message_type) is None:
            hint = _HANDLER_HINT.get(message_type, "the appropriate handler method")

            logger.warning(
                "No %s handler registered for WorkflowType=%s, RequestId=%s",
                message_type,
                workflow_type,
                payload.request_id,
            )

            user_message = (
                "This agent has no capability of handling file uploads."
                if message_type == "file"
                else (
                    f"No {message_type} handler registered for workflow type '{workflow_type}'. "
                    f"Use {hint} to register a handler."
                )
            )

            await MessageResponseHelper.send_simple_message(
                message=message,
                text=user_message,
                workflow_id=workflow_id,
                workflow_type=workflow_type,
            )
            return

        # Extract tenant ID from WorkflowId
        try:
            tenant_id = TenantContext.extract_tenant_id(workflow_id)
        except (WorkflowIdError, ValueError):
            logger.error("Failed to extract tenant ID from WorkflowId: %s", workflow_id)
            return

        logger.debug(
            "Processing message: ParticipantId=%s, Scope=%s, Hint=%s, Tenant=%s",
            payload.participant_id,
            payload.scope,
            payload.hint,
            tenant_id,
        )

        # Validate tenant isolation (matches C# MessageValidator.ValidateTenantIsolation)
        if not validate_tenant_isolation(tenant_id, metadata):
            await MessageResponseHelper.send_simple_message(
                message=message,
                text="Error: Tenant isolation violation.",
                workflow_id=workflow_id,
                workflow_type=workflow_type,
            )
            return

        # Validate agent name (matches C# MessageValidator.ValidateAgentName)
        if not validate_agent_name(
            payload.agent,
            metadata,
            payload.request_id or "",
        ):
            await MessageResponseHelper.send_simple_message(
                message=message,
                text=(
                    f"Error: Message intended for agent '{(payload.agent or '').strip()}' "
                    f"but received by '{metadata.agent_name}'."
                ),
                workflow_id=workflow_id,
                workflow_type=workflow_type,
            )
            return

        logger.debug(
            "Processing %s via activity: WorkflowType=%s, Agent=%s, Tenant=%s, SystemScoped=%s",
            message_type,
            workflow_type,
            metadata.agent_name,
            tenant_id,
            metadata.system_scoped,
        )

        request = ProcessMessageActivityRequest(
            message_text=payload.text or "",
            participant_id=payload.participant_id or "",
            request_id=payload.request_id or "",
            scope=payload.scope or "",
            hint=payload.hint or "",
            data=payload.data,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            authorization=payload.authorization,
            thread_id=payload.thread_id or "",
            message_type=message_type,
        )

        await workflow.execute_activity(
            "ProcessAndSendMessage",
            request,
            start_to_close_timeout=timedelta(minutes=5),
        )

        logger.debug(
            "%s processed and responses sent: RequestId=%s",
            message_type,
            payload.request_id,
        )
