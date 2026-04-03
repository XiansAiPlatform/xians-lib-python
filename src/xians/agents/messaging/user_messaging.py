"""UserMessaging - proactive (agent-initiated) messaging. Matches C# UserMessaging.

Use this when the agent needs to proactively send messages without a user message
context to reply to. For replying to user messages, use UserMessageContext instead.

Example usage (inside a workflow or activity):
    await UserMessaging.send_chat_async("user-123", "Your order has shipped!")
    await UserMessaging.send_data_async("user-123", "Order update", {"status": "shipped"})
    await UserMessaging.send_chat_as_workflow_async("Conversational", "user-123", "Content found!")
"""

import logging
import uuid
from datetime import timedelta
from typing import Any, Optional

from ...temporal_workflows.v1.models import SendMessageRequest

logger = logging.getLogger(__name__)

_STANDARD_ACTIVITY_TIMEOUT = timedelta(minutes=10)


class UserMessaging:
    """Static helper for sending agent-initiated messages to users.

    Matches C# UserMessaging. Works in both Temporal workflow and activity contexts:
    - In workflow context: executes via Temporal activity (deterministic)
    - In activity context: sends directly via MessageService (HTTP)

    Raises InvalidOperationError when called outside of workflow/activity context.
    """

    @staticmethod
    async def send_chat_async(
        participant_id: str,
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Send a chat message to a participant using the current workflow context."""
        await UserMessaging._send_message_async(
            participant_id, text, data, scope, hint, task_id, "chat"
        )

    @staticmethod
    async def send_data_async(
        participant_id: str,
        text: str,
        data: Any,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Send a data message to a participant using the current workflow context."""
        await UserMessaging._send_message_async(
            participant_id, text, data, scope, hint, task_id, "data"
        )

    @staticmethod
    async def send_reasoning_async(
        builtin_workflow_name: str,
        participant_id: str,
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Send a reasoning message while impersonating a builtin workflow."""
        await UserMessaging._send_message_as_workflow_async(
            builtin_workflow_name, participant_id, text, data, scope, hint, task_id, "reasoning"
        )

    @staticmethod
    async def send_tool_call_async(
        builtin_workflow_name: str,
        participant_id: str,
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Send a tool execution message while impersonating a builtin workflow."""
        await UserMessaging._send_message_as_workflow_async(
            builtin_workflow_name, participant_id, text, data, scope, hint, task_id, "tool"
        )

    @staticmethod
    async def send_chat_as_workflow_async(
        builtin_workflow_name: str,
        participant_id: str,
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Send a chat message while impersonating a different builtin workflow.

        Useful for sending messages from background workflows as if they came from
        the main conversational workflow.
        """
        await UserMessaging._send_message_as_workflow_async(
            builtin_workflow_name, participant_id, text, data, scope, hint, task_id, "chat"
        )

    @staticmethod
    async def send_data_as_workflow_async(
        builtin_workflow_name: str,
        participant_id: str,
        text: str,
        data: Any,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Send a data message while impersonating a different builtin workflow."""
        await UserMessaging._send_message_as_workflow_async(
            builtin_workflow_name, participant_id, text, data, scope, hint, task_id, "data"
        )

    @staticmethod
    async def get_last_task_id_async(
        participant_id: str,
        scope: Optional[str] = None,
    ) -> Optional[str]:
        """Retrieve the last task ID for a conversation.

        Works in both workflow and activity contexts.
        """
        from ...agents.core.xians_context import XiansContext

        if not participant_id or not participant_id.strip():
            raise ValueError("participant_id cannot be null or empty.")

        workflow_id = XiansContext.get_workflow_id() or ""
        tenant_id = XiansContext.get_tenant_id() or ""

        if UserMessaging._in_workflow():
            from temporalio import workflow as _wf
            return await _wf.execute_activity(
                "GetLastTaskId",
                args=[workflow_id, participant_id, scope or "", tenant_id],
                start_to_close_timeout=_STANDARD_ACTIVITY_TIMEOUT,
            )
        elif XiansContext.in_activity():
            svc = UserMessaging._get_message_service()
            return await svc.get_last_task_id_async(
                workflow_id=workflow_id,
                participant_id=participant_id,
                scope=scope or "",
                tenant_id=tenant_id,
            )
        else:
            raise RuntimeError(
                "UserMessaging can only be used within a Temporal workflow or activity context."
            )

    # ------------------------------------------------------------------
    # Private implementation
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_message_async(
        participant_id: str,
        text: str,
        data: Any,
        scope: Optional[str],
        hint: Optional[str],
        task_id: Optional[str],
        message_type: str,
    ) -> None:
        from ...agents.core.xians_context import XiansContext

        if not participant_id or not participant_id.strip():
            raise ValueError("participant_id cannot be null or empty.")

        workflow_id = XiansContext.get_workflow_id() or ""
        workflow_type = XiansContext._resolve_workflow_type() or ""
        tenant_id = XiansContext.get_tenant_id() or ""

        await UserMessaging._send_message_internal_async(
            workflow_id, workflow_type, tenant_id,
            participant_id, text, data, scope, hint, task_id, message_type,
        )

    @staticmethod
    async def _send_message_as_workflow_async(
        builtin_workflow_name: str,
        participant_id: str,
        text: str,
        data: Any,
        scope: Optional[str],
        hint: Optional[str],
        task_id: Optional[str],
        message_type: str,
    ) -> None:
        from ...agents.core.xians_context import XiansContext

        if not builtin_workflow_name or not builtin_workflow_name.strip():
            raise ValueError("builtin_workflow_name cannot be null or empty.")
        if not participant_id or not participant_id.strip():
            raise ValueError("participant_id cannot be null or empty.")

        tenant_id = XiansContext.get_tenant_id() or ""
        agent_name = XiansContext._resolve_agent_name() or ""

        workflow_type = XiansContext.build_workflow_type(agent_name, builtin_workflow_name)
        workflow_id = XiansContext.build_workflow_id(tenant_id, agent_name, builtin_workflow_name)

        await UserMessaging._send_message_internal_async(
            workflow_id, workflow_type, tenant_id,
            participant_id, text, data, scope, hint, task_id, message_type,
        )

    @staticmethod
    async def _send_message_internal_async(
        workflow_id: str,
        workflow_type: str,
        tenant_id: str,
        participant_id: str,
        text: str,
        data: Any,
        scope: Optional[str],
        hint: Optional[str],
        task_id: Optional[str],
        message_type: str,
    ) -> None:
        from ...agents.core.xians_context import XiansContext

        request_id: str
        if UserMessaging._in_workflow():
            from temporalio import workflow as _wf
            request_id = str(_wf.uuid4())
        else:
            request_id = str(uuid.uuid4())

        request = SendMessageRequest(
            participant_id=participant_id,
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            text=text,
            data=data,
            request_id=request_id,
            scope=scope or "",
            hint=hint or "",
            task_id=task_id,
            origin="agent-initiated",
            type=message_type,
            tenant_id=tenant_id,
        )

        if UserMessaging._in_workflow():
            from temporalio import workflow as _wf
            await _wf.execute_activity(
                "SendMessage",
                request,
                start_to_close_timeout=_STANDARD_ACTIVITY_TIMEOUT,
            )
        elif XiansContext.in_activity():
            svc = UserMessaging._get_message_service()
            await svc.send_async(request)
        else:
            raise RuntimeError(
                "UserMessaging can only be used within a Temporal workflow or activity context."
            )

    @staticmethod
    def _in_workflow() -> bool:
        try:
            from temporalio import workflow as _wf
            _wf.info()
            return True
        except Exception:
            return False

    @staticmethod
    def _get_message_service() -> "MessageService":
        """Create a MessageService from the current agent's HTTP client.

        Mirrors C#: new MessageService(agent.HttpService.Client, logger)
        The Python AgentRegistration exposes ``http_client`` which returns the
        platform's shared ``httpx.AsyncClient``.
        """
        from ...agents.core.xians_context import XiansContext
        from .message_service import MessageService

        agent = XiansContext.CurrentAgent

        # AgentRegistration.http_client → platform's shared httpx.AsyncClient
        client = getattr(agent, "http_client", None)
        if client is None:
            raise RuntimeError(
                "HTTP service not available for message operations. "
                "Ensure the agent is properly configured with a platform connection."
            )

        return MessageService(client)
