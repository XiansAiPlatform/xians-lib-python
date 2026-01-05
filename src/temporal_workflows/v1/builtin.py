"""Built-in workflow implementations for Xians SDK v1."""

from collections.abc import Callable
from typing import Any

from temporalio import workflow

from .base import BaseWorkflow


@workflow.defn
class ConversationalWorkflow(BaseWorkflow):

    def __init__(self) -> None:
        self.conversation_id: str | None = None
        self.handlers: dict[str, Callable[..., Any]] = {}

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        self.conversation_id = input_data.get("conversation_id")

        # Workflow logic will be expanded to handle signals and activities
        # This is a minimal implementation for the base structure

        return {
            "conversation_id": self.conversation_id,
            "status": "completed",
        }

    @workflow.signal
    async def handle_user_message(self, message: dict[str, Any]) -> None:
        # Signal handling logic will be implemented when we add the handler system
        pass

    def register_handler(self, event_type: str, handler: Callable[..., Any]) -> None:
        self.handlers[event_type] = handler


@workflow.defn
class TaskBasedWorkflow(BaseWorkflow):

    def __init__(self) -> None:
        """Initialize the task-based workflow."""
        self.task_id: str | None = None
        self.handlers: dict[str, Callable[..., Any]] = {}

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        self.task_id = input_data.get("task_id")

        # Workflow logic will be expanded to handle activities and retries
        # This is a minimal implementation for the base structure

        return {
            "task_id": self.task_id,
            "status": "completed",
        }

    @workflow.signal
    async def cancel_task(self) -> None:
        # Cancellation logic will be implemented
        pass

    def register_handler(self, task_type: str, handler: Callable[..., Any]) -> None:
        self.handlers[task_type] = handler


__all__ = ["ConversationalWorkflow", "TaskBasedWorkflow"]
