"""Entity models for Xians SDK v1.

Aligned with C# XiansAgentRegistration and related models.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from ...constants.v1.core import MessageRole, WorkflowType


class XiansAgentRegistration(BaseModel):
    """Registration DTO matching C# XiansAgentRegistration.

    Used to register an agent with the platform, including metadata
    for the agent definition upload.
    """

    name: str = Field(min_length=1, description="Agent name (no ':' allowed)")
    is_template: bool = Field(default=False, description="True = system-scoped template")
    description: Optional[str] = Field(default=None, description="Agent description")
    summary: Optional[str] = Field(default=None, description="Short summary")
    version: Optional[str] = Field(default=None, description="Agent version")
    author: Optional[str] = Field(default=None, description="Author name")
    category: Optional[str] = Field(default=None, description="Agent category")
    enable_tasks: bool = Field(default=False, description="Enable HITL task workflows")

    model_config = {"frozen": False}

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Agent name cannot be empty")
        if ":" in v:
            raise ValueError("Agent name cannot contain ':'")
        return v

    @property
    def system_scoped(self) -> bool:
        return self.is_template


class LLMMessage(BaseModel):
    """Represents a single message in an LLM conversation."""

    role: MessageRole = Field(description="Role of the message sender")
    content: str = Field(description="Text content of the message")
    name: str | None = Field(default=None, description="Optional name identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {"frozen": False}


class LLMResponse(BaseModel):
    """Represents a response from an LLM provider."""

    text: str = Field(description="Generated text response")
    model: str = Field(description="Model identifier")
    finish_reason: str = Field(description="Reason generation finished")
    usage: dict[str, int] = Field(default_factory=dict, description="Token usage statistics")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {"frozen": False}


class AgentDefinition(BaseModel):
    """Defines an agent in the Xians platform.

    Kept for backward compatibility; prefer XiansAgentRegistration for new code.
    """

    name: str = Field(min_length=1, description="Unique agent name")
    description: str | None = Field(default=None, description="Agent description")
    system_scoped: bool = Field(default=False, description="Whether agent is system-scoped")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    agent_key: str | None = Field(default=None, description="Generated unique key")
    version: str = Field(default="1.0.0", description="Agent version")
    hash: str | None = Field(default=None, description="Content hash for idempotency")

    model_config = {"frozen": False}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Agent name cannot be empty or whitespace")
        return v


class WorkflowDefinition(BaseModel):
    """Defines a workflow configuration.

    Kept for backward compatibility; the new XiansWorkflow class handles
    workflow definitions in the updated architecture.
    """

    workflow_type: WorkflowType = Field(description="Type of workflow")
    name: str = Field(description="Workflow instance name")
    workers: int = Field(default=1, description="Number of worker instances", ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional workflow configuration")
    agent_key: str | None = Field(default=None, description="Associated agent key")
    task_queue: str | None = Field(default=None, description="Temporal task queue name")
    activity_name: str = Field(default="execute_agent_activity", description="Activity function name")
    version: str = Field(default="1.0.0", description="Workflow version")
    hash: str | None = Field(default=None, description="Content hash for idempotency")

    model_config = {"frozen": False}


class ChatMessageContext(BaseModel):
    """Context provided to chat message handlers (legacy)."""

    message: LLMMessage = Field(description="The incoming message")
    conversation_id: str = Field(description="Conversation identifier")
    user_id: str | None = Field(default=None, description="User identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    model_config = {"frozen": False}


class AgentRequest(BaseModel):
    """Represents a request to execute an agent activity."""

    agent_key: str = Field(min_length=1, description="Unique agent identifier")
    conversation_id: str | None = Field(default=None, description="Optional conversation identifier")
    message: str | dict[str, Any] = Field(description="Input message")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")
    tenant_id: str | None = Field(default=None, description="Tenant identifier")
    system_scoped: bool = Field(default=False, description="Whether agent is system-scoped")
    idempotency_key: str | None = Field(default=None, description="Idempotency key")
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone(), description="Request timestamp")

    model_config = {"frozen": False}

    @field_validator("agent_key")
    @classmethod
    def validate_agent_key(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Agent key cannot be empty or whitespace")
        return v


class AgentResponse(BaseModel):
    """Represents a response from an agent activity execution."""

    text: str | None = Field(default=None, description="Text response")
    payload: dict[str, Any] | None = Field(default=None, description="Structured response payload")
    raw: Any | None = Field(default=None, description="Raw response data")
    usage: dict[str, int] | None = Field(default=None, description="Token/resource usage statistics")
    model: str | None = Field(default=None, description="Model identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")

    model_config = {"frozen": False}


__all__ = [
    "XiansAgentRegistration",
    "LLMMessage",
    "LLMResponse",
    "AgentDefinition",
    "WorkflowDefinition",
    "ChatMessageContext",
    "AgentRequest",
    "AgentResponse",
]
