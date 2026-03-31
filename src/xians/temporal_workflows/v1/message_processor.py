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
from .tenant_context import TenantContext

logger = logging.getLogger(__name__)

# Message type to registration hint (matches C# handler registration method names)
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
        workflow_run_id: str | None,
    ) -> None:
        """Process a single inbound message.

        1. Validate message type
        2. Look up handler
        3. Validate tenant isolation and agent name
        4. Execute message activity
        """
        payload = message.payload
        message_type = (payload.type or "").lower()

        if message_type not in ("chat", "data", "file", "webhook"):
            logger.warning(f"Skipping unknown message type: {message_type}")
            return

        from .workflows import _handlers_by_workflow_type

        metadata = _handlers_by_workflow_type.get(workflow_type)

        if metadata is None:
            await MessageResponseHelper.send_simple_message(
                message=message,
                text="No handlers registered for this workflow",
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
            if message_type != "webhook":
                hint = _HANDLER_HINT.get(message_type, "the appropriate handler method")
                await MessageResponseHelper.send_simple_message(
                    message=message,
                    text=(
                        f"No {message_type} handler registered for workflow type '{workflow_type}'. "
                        f"Use {hint} to register a handler."
                    ),
                    workflow_id=workflow_id,
                    workflow_type=workflow_type,
                )
            return

        tenant_id = TenantContext.extract_tenant_id(workflow_id)
        if tenant_id is None:
            logger.error("Failed to extract tenant ID from workflow_id=%s", workflow_id)
            return

        # Validate tenant isolation (matches C# MessageValidator.ValidateTenantIsolation)
        if not validate_tenant_isolation(tenant_id, metadata):
            logger.error(
                "Tenant isolation violation: workflow_tenant_id=%s metadata_tenant_id=%s",
                tenant_id,
                metadata.tenant_id,
            )
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

        # Debug: log payload and participant_id to troubleshoot participant routing
        logger.info(
            "[DEBUG] MessageProcessor building ProcessMessageActivityRequest",
            extra={
                "message_type": message_type,
                "participant_id": payload.participant_id,
                "participantId_raw": getattr(payload, "participantId", ""),
                "request_id": payload.request_id,
                "workflow_id": workflow_id,
                "workflow_type": workflow_type,
            },
        )
        logger.debug("[DEBUG] Full inbound payload: %s", payload.__dict__ if hasattr(payload, "__dict__") else str(payload))

        request = ProcessMessageActivityRequest(
            message_text=payload.text or "",
            participant_id=payload.participant_id or "",
            request_id=payload.request_id or "",
            scope=payload.scope or "",
            hint=payload.hint or "",
            data=payload.data,
            tenant_id=tenant_id or "",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            workflow_run_id=workflow_run_id,
            authorization=payload.authorization,
            thread_id=payload.thread_id or "",
            message_type=message_type,
        )

        await workflow.execute_activity(
            "ProcessAndSendMessage",
            request,
            start_to_close_timeout=timedelta(minutes=5),
        )
