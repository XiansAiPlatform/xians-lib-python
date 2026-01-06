"""Agent client for interacting with Temporal workflows."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from temporalio.client import Client, WorkflowHandle

from ...exceptions.v1.errors import TemporalError
from ...models.v1.entities import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)


class AgentClient:
    """
    Client for invoking and interacting with agent workflows.

    Provides methods for:
    - Invoking one-shot agent executions
    - Sending updates to conversational workflows
    - Sending signals to conversational workflows
    - Querying workflow state
    """

    def __init__(self, temporal_client: Client) -> None:
        """
        Initialize agent client.

        Args:
            temporal_client: Connected Temporal client.
        """
        self.client = temporal_client

    async def invoke(
        self,
        workflow_id: str,
        task_queue: str,
        request: AgentRequest,
        workflow_type: str = "InvokeAgentWorkflow",
        timeout: timedelta = timedelta(minutes=5),
    ) -> AgentResponse:
        """
        Invoke a one-shot agent execution.

        Args:
            workflow_id: Unique workflow identifier.
            task_queue: Task queue name.
            request: The agent request.
            workflow_type: Workflow type name (default: InvokeAgentWorkflow).
            timeout: Workflow execution timeout.

        Returns:
            The agent's response.

        Raises:
            TemporalError: If workflow execution fails.
        """
        try:
            handle = await self.client.start_workflow(
                workflow_type,
                request,
                id=workflow_id,
                task_queue=task_queue,
                execution_timeout=timeout,
            )

            logger.info(f"Started workflow {workflow_id} on queue {task_queue}")

            result = await handle.result()
            logger.info(f"Workflow {workflow_id} completed successfully")

            return result

        except Exception as e:
            raise TemporalError(
                f"Failed to invoke workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def start_conversation(
        self,
        workflow_id: str,
        task_queue: str,
        agent_key: str,
        conversation_id: str,
        workflow_type: str = "ConversationWorkflow",
    ) -> WorkflowHandle:
        """
        Start a long-running conversation workflow.

        Args:
            workflow_id: Unique workflow identifier.
            task_queue: Task queue name.
            agent_key: The agent identifier.
            conversation_id: The conversation identifier.
            workflow_type: Workflow type name (default: ConversationWorkflow).

        Returns:
            Handle to the running workflow.

        Raises:
            TemporalError: If workflow start fails.
        """
        try:
            handle = await self.client.start_workflow(
                workflow_type,
                args=[agent_key, conversation_id],
                id=workflow_id,
                task_queue=task_queue,
            )

            logger.info(
                f"Started conversation workflow {workflow_id} "
                f"for agent {agent_key}, conversation {conversation_id}"
            )

            return handle

        except Exception as e:
            raise TemporalError(
                f"Failed to start conversation workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def send_signal(
        self,
        workflow_id: str,
        signal_name: str,
        *args: Any,
    ) -> None:
        """
        Send a signal to a running workflow.

        Args:
            workflow_id: The workflow identifier.
            signal_name: The signal name.
            *args: Signal arguments.

        Raises:
            TemporalError: If signal send fails.
        """
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.signal(signal_name, *args)

            logger.debug(f"Sent signal {signal_name} to workflow {workflow_id}")

        except Exception as e:
            raise TemporalError(
                f"Failed to send signal to workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def send_update(
        self,
        workflow_id: str,
        update_name: str,
        *args: Any,
    ) -> Any:
        """
        Send an update to a running workflow and wait for result.

        Args:
            workflow_id: The workflow identifier.
            update_name: The update name.
            *args: Update arguments.

        Returns:
            The update result.

        Raises:
            TemporalError: If update fails.
        """
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            result = await handle.execute_update(update_name, *args)

            logger.debug(f"Sent update {update_name} to workflow {workflow_id}")
            return result

        except Exception as e:
            raise TemporalError(
                f"Failed to send update to workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def query(
        self,
        workflow_id: str,
        query_name: str,
        *args: Any,
    ) -> Any:
        """
        Query a running workflow.

        Args:
            workflow_id: The workflow identifier.
            query_name: The query name.
            *args: Query arguments.

        Returns:
            The query result.

        Raises:
            TemporalError: If query fails.
        """
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            result = await handle.query(query_name, *args)

            logger.debug(f"Queried workflow {workflow_id} with {query_name}")
            return result

        except Exception as e:
            raise TemporalError(
                f"Failed to query workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def cancel_workflow(self, workflow_id: str) -> None:
        """
        Cancel a running workflow.

        Args:
            workflow_id: The workflow identifier.

        Raises:
            TemporalError: If cancellation fails.
        """
        try:
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.cancel()

            logger.info(f"Cancelled workflow {workflow_id}")

        except Exception as e:
            raise TemporalError(
                f"Failed to cancel workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def get_workflow_result(
        self,
        workflow_id: str,
        timeout: timedelta | None = None,
    ) -> Any:
        """
        Get the result of a workflow execution.

        Args:
            workflow_id: The workflow identifier.
            timeout: Optional timeout for waiting.

        Returns:
            The workflow result.

        Raises:
            TemporalError: If getting result fails.
        """
        try:
            handle = self.client.get_workflow_handle(workflow_id)

            if timeout:
                result = await asyncio.wait_for(handle.result(), timeout=timeout.total_seconds())
            else:
                result = await handle.result()

            logger.info(f"Retrieved result for workflow {workflow_id}")
            return result

        except Exception as e:
            raise TemporalError(
                f"Failed to get result for workflow {workflow_id}: {str(e)}",
                cause=e,
            )


__all__ = ["AgentClient"]

