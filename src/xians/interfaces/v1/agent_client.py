"""Agent client for interacting with Temporal workflows."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from temporalio.client import Client, WorkflowHandle

from ...exceptions.v1.errors import AgentExecutionError, TemporalError
from ...models.v1.entities import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)


class AgentClient:
    """
    Client for invoking and interacting with agent workflows.
    """

    def __init__(self, temporal_client: Client) -> None:
        self.client = temporal_client

    @staticmethod
    def _is_error_response(response: AgentResponse) -> bool:
        """
        Check if an AgentResponse represents an error.
        """
        metadata = response.metadata
        return metadata.get("is_error") is True or "error" in metadata

    async def invoke(
        self,
        workflow_id: str,
        task_queue: str,
        request: AgentRequest,
        workflow_type: str = "InvokeAgentWorkflow",
        timeout: timedelta = timedelta(minutes=5),
        raise_on_agent_error: bool = False,
    ) -> AgentResponse:
        """
        Invoke an agent workflow and return the response.
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

            if isinstance(result, AgentResponse) and self._is_error_response(result):
                error_msg = result.metadata.get("error", "Unknown error")
                error_details = result.metadata.get("error_details", {})

                retry_after = error_details.get("provider_retry_after_seconds")
                retry_info = f" (retry after {retry_after}s)" if retry_after else ""

                logger.error(
                    f"Workflow {workflow_id} completed with agent error: {error_msg}{retry_info}"
                )

                if raise_on_agent_error:
                    raise AgentExecutionError(
                        error_msg,
                        workflow_id=workflow_id,
                        task_queue=task_queue,
                        error_details=error_details,
                    )
            else:
                logger.info(f"Workflow {workflow_id} completed successfully")

            return result

        except AgentExecutionError:
            raise
        except Exception as e:
            raise TemporalError(
                f"Failed to invoke workflow {workflow_id}: {str(e)}",
                cause=e,
            )

    async def invoke_or_raise(
        self,
        workflow_id: str,
        task_queue: str,
        request: AgentRequest,
        workflow_type: str = "InvokeAgentWorkflow",
        timeout: timedelta = timedelta(minutes=5),
    ) -> AgentResponse:
        """
        Invoke an agent workflow, raising an exception on agent errors.
        """
        return await self.invoke(
            workflow_id=workflow_id,
            task_queue=task_queue,
            request=request,
            workflow_type=workflow_type,
            timeout=timeout,
            raise_on_agent_error=True,
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

