"""Core constants and enumerations for Xians SDK v1."""

from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    CUSTOM = "custom"
    GOOGLE_VERTEX = "google_vertex"
    MICROSOFT_AGENT = "microsoft_agent"
    AWS_BEDROCK = "aws_bedrock"


class WorkflowType(str, Enum):
    CONVERSATIONAL = "Conversational"
    TASK_BASED = "TaskBased"
    REACTIVE = "Reactive"
    CUSTOM = "Custom"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    TERMINATED = "terminated"


class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_LLM_MAX_TOKENS = 2048

XIANS_API_BASE_PATH = "/api/v1"
XIANS_AGENT_PATH = f"{XIANS_API_BASE_PATH}/agents"
XIANS_WORKFLOW_PATH = f"{XIANS_API_BASE_PATH}/workflows"
XIANS_KNOWLEDGE_PATH = f"{XIANS_API_BASE_PATH}/knowledge"
XIANS_DOCUMENT_PATH = f"{XIANS_API_BASE_PATH}/documents"
XIANS_CONVERSATION_PATH = f"{XIANS_API_BASE_PATH}/conversations"
XIANS_USAGE_PATH = f"{XIANS_API_BASE_PATH}/usage"
XIANS_CONFIG_PATH = f"{XIANS_API_BASE_PATH}/config"

__all__ = [
    "LLMProvider",
    "WorkflowType",
    "MessageRole",
    "AgentStatus",
    "WorkflowStatus",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_RETRY_ATTEMPTS",
    "DEFAULT_HTTP_TIMEOUT_SECONDS",
    "DEFAULT_LLM_TEMPERATURE",
    "DEFAULT_LLM_MAX_TOKENS",
    "XIANS_API_BASE_PATH",
    "XIANS_AGENT_PATH",
    "XIANS_WORKFLOW_PATH",
    "XIANS_KNOWLEDGE_PATH",
    "XIANS_DOCUMENT_PATH",
    "XIANS_CONVERSATION_PATH",
    "XIANS_USAGE_PATH",
    "XIANS_CONFIG_PATH",
]
