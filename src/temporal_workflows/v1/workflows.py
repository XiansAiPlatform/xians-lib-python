"""Built-in Temporal workflows for Xians SDK v1."""

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from ...models.v1.entities import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)


@workflow.defn
class InvokeAgentWorkflow:
    """
    Simple invoke workflow for stateless agent execution.

    This workflow executes a single agent activity and returns the result.
    It's designed for request-response patterns without session state.
    """

    @workflow.run
    async def run(self, request: AgentRequest) -> AgentResponse:
        """
        Execute a single agent request.

        Args:
            request: The agent request to process.

        Returns:
            The agent's response.
        """
        workflow.logger.info(
            f"InvokeAgentWorkflow started for agent: {request.agent_key}, "
            f"conversation: {request.conversation_id}"
        )

        # Get activity name from workflow memo or use default
        activity_name = workflow.memo_value("activity_name", default="execute_agent_activity")

        # Execute the agent activity with retries
        try:
            response = await workflow.execute_activity(
                activity_name,
                request,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                    non_retryable_error_types=["ValueError", "ValidationError"],
                ),
            )

            workflow.logger.info(f"InvokeAgentWorkflow completed for agent: {request.agent_key}")
            return response

        except Exception as e:
            workflow.logger.error(
                f"InvokeAgentWorkflow failed for agent {request.agent_key}: {str(e)}"
            )
            # Return error response instead of raising
            return AgentResponse(
                text=f"Agent execution failed: {str(e)}",
                metadata={"error": str(e), "error_type": type(e).__name__},
            )


@workflow.defn
class ConversationWorkflow:
    """
    Long-running conversational workflow with session state.

    This workflow maintains a conversation session and handles:
    - Signals for fire-and-forget messages
    - Updates for request-response interactions
    - Query for session state inspection
    """

    def __init__(self) -> None:
        """Initialize conversation state."""
        self._messages: list[dict[str, Any]] = []
        self._session_metadata: dict[str, Any] = {}
        self._activity_name = "execute_agent_activity"

    @workflow.run
    async def run(self, agent_key: str, conversation_id: str) -> dict[str, Any]:
        """
        Start and maintain a conversation session.

        Args:
            agent_key: The agent identifier.
            conversation_id: The conversation identifier.

        Returns:
            Final session summary.
        """
        workflow.logger.info(
            f"ConversationWorkflow started for agent: {agent_key}, "
            f"conversation: {conversation_id}"
        )

        self._session_metadata = {
            "agent_key": agent_key,
            "conversation_id": conversation_id,
            "started_at": workflow.now().isoformat(),
        }

        # Get activity name from memo if provided
        self._activity_name = workflow.memo_value(
            "activity_name", default="execute_agent_activity"
        )

        # Wait indefinitely - workflow is controlled by signals/updates or external cancellation
        await workflow.wait_condition(lambda: False)

        return {
            "conversation_id": conversation_id,
            "message_count": len(self._messages),
            "metadata": self._session_metadata,
        }

    @workflow.signal
    async def inbound_message(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        """
        Handle an inbound message (fire-and-forget).

        Args:
            message: The message text.
            metadata: Optional message metadata.
        """
        workflow.logger.info(f"Received inbound message for conversation workflow")

        self._messages.append(
            {
                "message": message,
                "metadata": metadata or {},
                "timestamp": workflow.now().isoformat(),
                "direction": "inbound",
            }
        )

        # Create agent request
        request = AgentRequest(
            agent_key=self._session_metadata["agent_key"],
            conversation_id=self._session_metadata["conversation_id"],
            message=message,
            metadata=metadata or {},
        )

        # Execute agent activity (fire and forget - no await needed for signal)
        # Note: In signals, we typically don't await activities directly
        # Instead, we'd use workflow.start_activity or queue the message
        # For now, we'll just log it
        workflow.logger.debug(f"Message queued for processing: {message[:50]}...")

    @workflow.update
    async def request_response(
        self, message: str, metadata: dict[str, Any] | None = None
    ) -> AgentResponse:
        """
        Handle a request-response message interaction.

        Args:
            message: The message text.
            metadata: Optional message metadata.

        Returns:
            The agent's response.
        """
        workflow.logger.info(f"Processing request_response for conversation workflow")

        self._messages.append(
            {
                "message": message,
                "metadata": metadata or {},
                "timestamp": workflow.now().isoformat(),
                "direction": "inbound",
            }
        )

        # Create agent request
        request = AgentRequest(
            agent_key=self._session_metadata["agent_key"],
            conversation_id=self._session_metadata["conversation_id"],
            message=message,
            metadata=metadata or {},
        )

        # Execute the agent activity
        try:
            response = await workflow.execute_activity(
                self._activity_name,
                request,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                    non_retryable_error_types=["ValueError", "ValidationError"],
                ),
            )

            # Record response
            self._messages.append(
                {
                    "message": response.text or str(response.payload),
                    "metadata": response.metadata,
                    "timestamp": workflow.now().isoformat(),
                    "direction": "outbound",
                }
            )

            return response

        except Exception as e:
            workflow.logger.error(f"Agent activity failed: {str(e)}")
            return AgentResponse(
                text=f"Agent execution failed: {str(e)}",
                metadata={"error": str(e), "error_type": type(e).__name__},
            )

    @workflow.query
    def get_session_state(self) -> dict[str, Any]:
        """
        Query the current session state.

        Returns:
            Current session metadata and message count.
        """
        return {
            "metadata": self._session_metadata,
            "message_count": len(self._messages),
            "last_message_at": (
                self._messages[-1]["timestamp"] if self._messages else None
            ),
        }

    @workflow.query
    def get_message_history(self) -> list[dict[str, Any]]:
        """
        Query the message history.

        Returns:
            List of all messages in the conversation.
        """
        return self._messages


__all__ = ["InvokeAgentWorkflow", "ConversationWorkflow"]

