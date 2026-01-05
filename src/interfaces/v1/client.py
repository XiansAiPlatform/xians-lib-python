from abc import ABC, abstractmethod
from typing import Any

from src.models.v1 import WorkflowDefinition


class IXiansClient(ABC):
    """Interface for communicating with the Xians platform backend."""

    @abstractmethod
    async def fetch_temporal_settings(self) -> dict[str, Any]:
        """Fetch Temporal connection settings from the platform."""
        raise NotImplementedError

    @abstractmethod
    async def upload_workflow_definition(self, definition: WorkflowDefinition) -> str:
        """Upload a workflow definition and return its server identifier."""
        raise NotImplementedError

    @abstractmethod
    async def send_usage_event(self, event: dict[str, Any]) -> None:
        """Send a usage or telemetry event to the platform."""
        raise NotImplementedError

    @abstractmethod
    async def send_outbound_message(self, payload: dict[str, Any]) -> None:
        """Send an outbound message (e.g., conversation or notification)."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_knowledge(self, query: dict[str, Any]) -> dict[str, Any]:
        """Retrieve knowledge or documents based on a query."""
        raise NotImplementedError


__all__ = ["IXiansClient"]
