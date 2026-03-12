"""Base classes for Temporal workflows (deprecated).

The BuiltinWorkflow in workflows.py is now the primary workflow implementation.
This file is kept for backward compatibility only.
"""

from abc import ABC, abstractmethod
from typing import Any

from temporalio import workflow


class BaseWorkflow(ABC):
    @abstractmethod
    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement run method")


__all__ = ["BaseWorkflow"]
