"""Entity models for Xians SDK v1."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from ...constants.v1.core import MessageRole, WorkflowType


class LLMMessage(BaseModel):
    """
    Represents a single message in an LLM conversation.

    Attributes:
        role: The role of the message sender (system, user, assistant, etc.).
        content: The text content of the message.
        name: Optional name identifier for the message sender.
        metadata: Additional metadata for the message.
    """

    role: MessageRole = Field(description="Role of the message sender")
    content: str = Field(description="Text content of the message")
    name: str | None = Field(default=None, description="Optional name identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    model_config = {"frozen": False}


class LLMResponse(BaseModel):
    """
    Represents a response from an LLM provider.

    Attributes:
        text: The generated text response.
        model: The model identifier that generated the response.
        finish_reason: The reason the generation finished (e.g., 'stop', 'length').
        usage: Token usage statistics for the request.
        metadata: Additional provider-specific metadata.
    """

    text: str = Field(description="Generated text response")
    model: str = Field(description="Model identifier")
    finish_reason: str = Field(description="Reason generation finished")
    usage: dict[str, int] = Field(
        default_factory=dict,
        description="Token usage statistics",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    model_config = {"frozen": False}


class AgentDefinition(BaseModel):
    """
    Defines an agent in the Xians platform.

    Attributes:
        name: Unique name for the agent (must be non-empty).
        description: Optional description of the agent's purpose.
        system_scoped: Whether the agent is system-scoped or user-scoped.
        metadata: Additional metadata for the agent.
    """

    name: str = Field(min_length=1, description="Unique agent name")
    description: str | None = Field(default=None, description="Agent description")
    system_scoped: bool = Field(
        default=False,
        description="Whether agent is system-scoped",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    model_config = {"frozen": False}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name is non-empty after stripping whitespace."""
        if not v.strip():
            raise ValueError("Agent name cannot be empty or whitespace")
        return v


class WorkflowDefinition(BaseModel):
    """
    Defines a workflow configuration.

    Attributes:
        workflow_type: The type of workflow (Conversational, TaskBased, etc.).
        name: Name for the workflow instance.
        workers: Number of worker instances (must be >= 1).
        metadata: Additional workflow configuration metadata.
    """

    workflow_type: WorkflowType = Field(description="Type of workflow")
    name: str = Field(description="Workflow instance name")
    workers: int = Field(default=1, description="Number of worker instances", ge=1)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional workflow configuration",
    )

    model_config = {"frozen": False}


class ChatMessageContext(BaseModel):
    """
    Context provided to chat message handlers.

    Attributes:
        message: The incoming message.
        conversation_id: Unique identifier for the conversation.
        user_id: Identifier for the user sending the message.
        metadata: Additional context metadata.
    """

    message: LLMMessage = Field(description="The incoming message")
    conversation_id: str = Field(description="Conversation identifier")
    user_id: str | None = Field(default=None, description="User identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context",
    )

    model_config = {"frozen": False}


__all__ = [
    "LLMMessage",
    "LLMResponse",
    "AgentDefinition",
    "WorkflowDefinition",
    "ChatMessageContext",
]
