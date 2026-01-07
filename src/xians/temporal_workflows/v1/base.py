"""Base classes for Temporal workflows in Xians SDK v1."""

from abc import ABC, abstractmethod
from typing import Any

from temporalio import workflow


class BaseWorkflow(ABC):
    @abstractmethod
    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement run method")


__all__ = ["BaseWorkflow"]
