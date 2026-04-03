"""UserMessageContext - rich context for chat/data/file handlers.

Matches C# UserMessageContext / ActivityUserMessageContext.
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from ...agents.core.xians_context import XiansContext
from ...temporal_workflows.v1.models import (
    CurrentMessage,
    ProcessMessageActivityRequest,
    SendMessageRequest,
    SendHandoffRequest,
    DbMessage,
)

if TYPE_CHECKING:
    from .message_service import MessageService


class UserMessageContext:
    """Context passed to chat/data/file handlers. Matches C# UserMessageContext.

    Provides message details, reply methods, history retrieval, and handoff capability.
    """

    def __init__(
        self,
        request: ProcessMessageActivityRequest,
        message_service: MessageService,
    ):
        self._request = request
        self._message_service = message_service
        self._metadata = request.metadata
        self.skip_response: bool = False

        self.message = CurrentMessage(
            text=request.message_text,
            participant_id=request.participant_id,
            request_id=request.request_id,
            scope=request.scope,
            hint=request.hint,
            data=request.data,
            tenant_id=request.tenant_id,
            workflow_id=request.workflow_id,
            workflow_type=request.workflow_type,
            authorization=request.authorization,
            thread_id=request.thread_id,
            message_type=request.message_type,
        )

    @property
    def metadata(self) -> Optional[dict[str, str]]:
        return self._metadata

    @property
    def metrics(self):
        """Fluent builder for tracking metrics with automatic context from this message.

        Matches C# context.Metrics. Use from message handlers:
            await context.metrics
                .with_metric("tokens", "total", 150, "tokens")
                .report_async()
        """
        from ...agents.metrics import ContextAwareUsageReportBuilder

        agent = XiansContext.CurrentAgent
        return agent.metrics.track(self)

    async def reply_async(self, text: str, data: Any = None) -> None:
        """Send a chat reply to the user."""
        if self.skip_response:
            return
        request = self._build_send_request(text=text, data=data, msg_type="chat")
        await self._message_service.send_async(request)

    async def send_data_async(self, data: Any, content: Optional[str] = None) -> None:
        """Send a data message."""
        request = self._build_send_request(text=content or "", data=data, msg_type="data")
        await self._message_service.send_async(request)

    async def send_reasoning_async(self, data: Any, content: Optional[str] = None) -> None:
        """Send a reasoning message (for thought chain visibility)."""
        request = self._build_send_request(text=content or "", data=data, msg_type="reasoning")
        await self._message_service.send_async(request)

    async def send_tool_exec_async(self, data: Any, content: Optional[str] = None) -> None:
        """Send a tool execution message."""
        request = self._build_send_request(text=content or "", data=data, msg_type="tool")
        await self._message_service.send_async(request)

    async def get_chat_history_async(
        self, page: int = 1, page_size: int = 50
    ) -> list[DbMessage]:
        """Retrieve chat history for the conversation."""
        return await self._message_service.get_history_async(
            workflow_id=self.message.workflow_id,
            workflow_type=self.message.workflow_type,
            participant_id=self.message.participant_id,
            scope=self.message.scope,
            tenant_id=self.message.tenant_id,
            page=page,
            page_size=page_size,
        )

    async def get_last_task_id_async(self) -> Optional[str]:
        """Get the last HITL task ID for this conversation."""
        return await self._message_service.get_last_task_id_async(
            workflow_id=self.message.workflow_id,
            participant_id=self.message.participant_id,
            scope=self.message.scope,
            tenant_id=self.message.tenant_id,
        )

    async def send_handoff_async(
        self,
        target_workflow_id: str,
        message: Optional[str] = None,
        data: Any = None,
        user_message: Optional[str] = None,
    ) -> Optional[str]:
        """Hand off the conversation to another workflow.

        Args:
            target_workflow_id: The workflow ID to hand off to.
            message: Custom handoff message text. Falls back to current message text.
            data: Data to pass with handoff. Falls back to current message data.
            user_message: Optional message to send to the user before the handoff.
        """
        if not target_workflow_id:
            raise ValueError("target_workflow_id cannot be null or empty")

        if user_message:
            await self.reply_async(user_message)

        if not self.message.thread_id:
            raise RuntimeError("ThreadId is required for handoff operations")

        text = message or self.message.text or ""
        if not text:
            raise RuntimeError("Message text is required for handoff")

        agent_name = ""
        try:
            agent = XiansContext.CurrentAgent
            agent_name = getattr(agent, "name", "") or ""
        except Exception:
            pass

        request = SendHandoffRequest(
            target_workflow_id=target_workflow_id,
            target_workflow_type="",
            source_agent=agent_name,
            source_workflow_type=self.message.workflow_type,
            source_workflow_id=self.message.workflow_id,
            thread_id=self.message.thread_id,
            participant_id=self.message.participant_id,
            authorization=self.message.authorization,
            text=text,
            data=data if data is not None else self.message.data,
            tenant_id=self.message.tenant_id,
        )
        return await self._message_service.send_handoff_async(request)

    def _build_send_request(self, text: str, data: Any, msg_type: str) -> SendMessageRequest:
        """Build a SendMessageRequest from the current context.

        Falls back to Message.Data when data is None (matches C# BuildSendMessageRequest).
        """
        return SendMessageRequest(
            participant_id=self.message.participant_id,
            workflow_id=self.message.workflow_id,
            workflow_type=self.message.workflow_type,
            request_id=self.message.request_id,
            scope=self.message.scope,
            data=data if data is not None else self.message.data,
            authorization=self.message.authorization,
            text=text,
            thread_id=self.message.thread_id,
            hint=self.message.hint,
            type=msg_type,
            tenant_id=self.message.tenant_id,
        )
