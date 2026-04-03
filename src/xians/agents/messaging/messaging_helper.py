"""MessagingHelper - convenience facade for proactive messaging. Matches C# MessagingHelper.

Exposed via XiansContext.Messaging. Wraps UserMessaging with automatic participant ID
resolution from the current workflow context.

Example usage:
    # Inside any workflow or activity
    await XiansContext.Messaging.send_chat_async("Hello from the agent!")
    await XiansContext.Messaging.send_data_async("Update", {"status": "done"})
    await XiansContext.Messaging.send_chat_as_workflow_async("Conversational", "Found content!")
"""

from typing import Any, Optional

from .user_messaging import UserMessaging


SUPERVISOR_WORKFLOW = "Supervisor Workflow"


class MessagingHelper:
    """Helper for proactive user messaging operations. Matches C# MessagingHelper.

    All methods automatically resolve participant_id from XiansContext if not provided.
    For A2A (Agent-to-Agent) communication, a separate A2A helper would be used.
    """

    @staticmethod
    async def send_chat_async(
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a chat message to a participant from the current workflow.

        If participant_id is not provided, uses the participant ID from the current
        workflow context (set during message handler execution).
        """
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_chat_async(participant_id, text, data, scope, hint, task_id)

    @staticmethod
    async def send_data_async(
        text: str,
        data: Any,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a data message to a participant from the current workflow.

        If participant_id is not provided, uses the participant ID from context.
        """
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_data_async(participant_id, text, data, scope, hint, task_id)

    @staticmethod
    async def send_chat_as_workflow_async(
        builtin_workflow_name: str,
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a chat message while impersonating a different workflow.

        Useful for sending messages from background workflows as if they came
        from the main chat workflow.
        """
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_chat_as_workflow_async(
            builtin_workflow_name, participant_id, text, data, scope, hint, task_id,
        )

    @staticmethod
    async def send_data_as_workflow_async(
        builtin_workflow_name: str,
        text: str,
        data: Any,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a data message while impersonating a different workflow."""
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_data_as_workflow_async(
            builtin_workflow_name, participant_id, text, data, scope, hint, task_id,
        )

    @staticmethod
    async def send_chat_as_supervisor_async(
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a chat message impersonating the Supervisor Workflow."""
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_chat_as_workflow_async(
            SUPERVISOR_WORKFLOW, participant_id, text, data, scope, hint, task_id,
        )

    @staticmethod
    async def send_reasoning_as_supervisor_async(
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a reasoning message impersonating the Supervisor Workflow."""
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_reasoning_async(
            SUPERVISOR_WORKFLOW, participant_id, text, data, scope, hint, task_id,
        )

    @staticmethod
    async def send_tool_call_as_supervisor_async(
        text: str,
        data: Any = None,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a tool call message impersonating the Supervisor Workflow."""
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_tool_call_async(
            SUPERVISOR_WORKFLOW, participant_id, text, data, scope, hint, task_id,
        )

    @staticmethod
    async def send_data_as_supervisor_async(
        text: str,
        data: Any,
        scope: Optional[str] = None,
        hint: Optional[str] = None,
        task_id: Optional[str] = None,
        participant_id: Optional[str] = None,
    ) -> None:
        """Send a data message impersonating the Supervisor Workflow."""
        participant_id = participant_id or MessagingHelper._get_participant_id()
        await UserMessaging.send_data_as_workflow_async(
            SUPERVISOR_WORKFLOW, participant_id, text, data, scope, hint, task_id,
        )

    @staticmethod
    def _get_participant_id() -> str:
        from ...agents.core.xians_context import XiansContext
        pid = XiansContext.get_participant_id()
        if not pid:
            raise ValueError(
                "No participant_id available in context and none was provided. "
                "Either pass participant_id explicitly or ensure this is called "
                "from within a message handler context."
            )
        return pid
