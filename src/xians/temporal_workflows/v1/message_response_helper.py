"""Helper for sending message responses from workflows. Matches C# MessageResponseHelper."""

import logging
from datetime import timedelta

from temporalio import workflow

from .models import InboundMessage, SendMessageRequest
from .tenant_context import TenantContext

logger = logging.getLogger(__name__)


class MessageResponseHelper:
    """Utility for sending responses back to users from within workflows.
    Matches C# MessageResponseHelper.
    """

    @staticmethod
    async def send_simple_message(
        message: InboundMessage,
        text: str,
        workflow_id: str,
        workflow_type: str,
    ) -> None:
        """Send a simple text message back via activity."""
        tenant_id = TenantContext.extract_tenant_id(workflow_id) or ""

        request = SendMessageRequest(
            participant_id=message.payload.participantId or "",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            request_id=message.payload.requestId or "",
            scope=message.payload.scope or "",
            authorization=message.payload.authorization,
            text=text,
            thread_id=message.payload.threadId or "",
            hint=message.payload.hint or "",
            type="chat",
            tenant_id=tenant_id,
        )

        await workflow.execute_activity(
            "SendMessage",
            request,
            start_to_close_timeout=timedelta(minutes=1),
        )

    @staticmethod
    async def send_heartbeat_response(
        message: InboundMessage,
        workflow_id: str,
        workflow_type: str,
    ) -> None:
        """Send a heartbeat response indicating the agent worker is available.
        Matches C# MessageResponseHelper.SendHeartbeatResponseAsync.
        """
        tenant_id = TenantContext.extract_tenant_id(workflow_id) or ""

        request = SendMessageRequest(
            participant_id=message.payload.participantId or "",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            request_id=message.payload.requestId or "",
            scope=message.payload.scope or "",
            authorization=message.payload.authorization,
            text="",
            thread_id=message.payload.threadId or "",
            hint=message.payload.hint or "",
            data={"available": True},
            origin="heartbeat",
            type="data",
            tenant_id=tenant_id,
        )

        await workflow.execute_activity(
            "SendMessage",
            request,
            start_to_close_timeout=timedelta(minutes=1),
        )

    @staticmethod
    async def send_heartbeat_unavailable_response(
        message: InboundMessage,
        workflow_id: str,
        workflow_type: str,
        reason: str = "Agent worker not available",
    ) -> None:
        """Send a heartbeat response indicating the agent worker is unavailable.
        Matches C# MessageResponseHelper.SendHeartbeatUnavailableResponseAsync.
        """
        tenant_id = TenantContext.extract_tenant_id(workflow_id) or ""

        request = SendMessageRequest(
            participant_id=message.payload.participantId or "",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            request_id=message.payload.requestId or "",
            scope=message.payload.scope or "",
            authorization=message.payload.authorization,
            text="",
            thread_id=message.payload.threadId or "",
            hint=message.payload.hint or "",
            data={"available": False, "reason": reason},
            origin="heartbeat",
            type="data",
            tenant_id=tenant_id,
        )

        await workflow.execute_activity(
            "SendMessage",
            request,
            start_to_close_timeout=timedelta(minutes=1),
        )

    @staticmethod
    async def send_error_response(
        message: InboundMessage,
        error_message: str,
        workflow_id: str,
        workflow_type: str,
    ) -> None:
        """Send an error response back to the user."""
        await MessageResponseHelper.send_simple_message(
            message=message,
            text=f"Error processing message: {error_message}",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
        )
