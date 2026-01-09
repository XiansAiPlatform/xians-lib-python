"""Built-in Temporal workflows for Xians SDK v1."""

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from ...models.v1.entities import AgentRequest, AgentResponse
from .failure_unwrap import unwrap_temporal_failure

logger = logging.getLogger(__name__)


# Shared retry policy configuration
_DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError", "ValidationError"],
)

_DEFAULT_ACTIVITY_TIMEOUT = timedelta(minutes=5)


def _create_error_response(error: Exception) -> AgentResponse:
    """
    Create a standardized error response with full failure unwrapping.

    Unwraps Temporal exceptions to extract root cause and diagnostic details.

    Args:
        error: The exception to convert into an error response.

    Returns:
        AgentResponse with detailed error information in text and metadata.
    """
    # Unwrap the error to get root cause and details
    error_details = unwrap_temporal_failure(error)

    root_type = error_details["root_error_type"]
    root_message = error_details["root_error_message"]

    # Create human-readable text with root cause
    error_text = f"Agent execution failed ({root_type}): {root_message}"

    # Build structured metadata
    metadata = {
        "is_error": True,
        "error": root_message,
        "error_type": root_type,
        "error_details": error_details,
    }

    return AgentResponse(
        text=error_text,
        metadata=metadata,
    )


@workflow.defn
class InvokeAgentWorkflow:
    """
    Simple invoke workflow for stateless agent execution.

    """

    @workflow.run
    async def run(self, request: AgentRequest) -> AgentResponse:
        """
        Execute a single agent request.

        """
        workflow.logger.info(
            f"InvokeAgentWorkflow started for agent: {request.agent_key}, "
            f"conversation: {request.conversation_id}"
        )

        activity_name = workflow.memo_value("activity_name", default="execute_agent_activity")

        try:
            response = await workflow.execute_activity(
                activity_name,
                request,
                start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY_POLICY,
            )

            workflow.logger.info(f"InvokeAgentWorkflow completed for agent: {request.agent_key}")
            return response

        except Exception as e:
            workflow.logger.error(
                f"InvokeAgentWorkflow failed for agent {request.agent_key}: {str(e)}"
            )
            return _create_error_response(e)


@workflow.defn
class ConversationWorkflow:
    """
    Long-running conversational workflow with session state.
    """

    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []
        self._session_metadata: dict[str, Any] = {}
        self._activity_name = "execute_agent_activity"

    def _record_message(
        self, message: str, metadata: dict[str, Any], direction: str
    ) -> None:
        """
        Record a message in the conversation history.
        """
        self._messages.append(
            {
                "message": message,
                "metadata": metadata,
                "timestamp": workflow.now().isoformat(),
                "direction": direction,
            }
        )

    def _create_agent_request(
        self, message: str, metadata: dict[str, Any]
    ) -> AgentRequest:
        """
        Create an AgentRequest from message data.

        """
        return AgentRequest(
            agent_key=self._session_metadata["agent_key"],
            conversation_id=self._session_metadata["conversation_id"],
            message=message,
            metadata=metadata,
        )

    @workflow.run
    async def run(self, agent_key: str, conversation_id: str) -> dict[str, Any]:
        """
        Start and maintain a conversation session.
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

        self._activity_name = workflow.memo_value(
            "activity_name", default="execute_agent_activity"
        )

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

        """
        workflow.logger.info(f"Received inbound message for conversation workflow")

        metadata = metadata or {}
        self._record_message(message, metadata, "inbound")
        request = self._create_agent_request(message, metadata)

        workflow.logger.debug(f"Message queued for processing: {message[:50]}...")

    @workflow.update
    async def request_response(
        self, message: str, metadata: dict[str, Any] | None = None
    ) -> AgentResponse:
        """
        Handle a request-response message interaction.
        """
        workflow.logger.info(f"Processing request_response for conversation workflow")

        metadata = metadata or {}
        self._record_message(message, metadata, "inbound")

        request = self._create_agent_request(message, metadata)

        try:
            response = await workflow.execute_activity(
                self._activity_name,
                request,
                start_to_close_timeout=_DEFAULT_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY_POLICY,
            )

            self._record_message(
                response.text or str(response.payload),
                response.metadata,
                "outbound"
            )

            return response

        except Exception as e:
            workflow.logger.error(f"Agent activity failed: {str(e)}")
            return _create_error_response(e)

    @workflow.query
    def get_session_state(self) -> dict[str, Any]:
        """
        Query the current session state.
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

        """
        return self._messages


__all__ = ["InvokeAgentWorkflow", "ConversationWorkflow"]

