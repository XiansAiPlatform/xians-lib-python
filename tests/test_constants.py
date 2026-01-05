"""
Unit tests for constants and enums.
"""

import pytest

from src.constants.v1.core import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT_SECONDS,
    XIANS_AGENT_PATH,
    XIANS_API_BASE_PATH,
    XIANS_CONVERSATION_PATH,
    XIANS_DOCUMENT_PATH,
    XIANS_KNOWLEDGE_PATH,
    XIANS_WORKFLOW_PATH,
    AgentStatus,
    LLMProvider,
    MessageRole,
    WorkflowStatus,
    WorkflowType,
)


@pytest.mark.unit
def test_llm_provider_enum() -> None:
    """Test LLMProvider enum values."""
    assert LLMProvider.OPENAI == "openai"
    assert LLMProvider.ANTHROPIC == "anthropic"
    assert LLMProvider.AZURE_OPENAI == "azure_openai"
    assert LLMProvider.CUSTOM == "custom"


@pytest.mark.unit
def test_workflow_type_enum() -> None:
    """Test WorkflowType enum values."""
    assert WorkflowType.CONVERSATIONAL == "Conversational"
    assert WorkflowType.TASK_BASED == "TaskBased"
    assert WorkflowType.REACTIVE == "Reactive"
    assert WorkflowType.CUSTOM == "Custom"


@pytest.mark.unit
def test_message_role_enum() -> None:
    """Test MessageRole enum values."""
    assert MessageRole.SYSTEM == "system"
    assert MessageRole.USER == "user"
    assert MessageRole.ASSISTANT == "assistant"
    assert MessageRole.FUNCTION == "function"
    assert MessageRole.TOOL == "tool"


@pytest.mark.unit
def test_agent_status_enum() -> None:
    """Test AgentStatus enum values."""
    assert AgentStatus.ACTIVE == "active"
    assert AgentStatus.INACTIVE == "inactive"
    assert AgentStatus.FAILED == "failed"
    assert AgentStatus.TERMINATED == "terminated"


@pytest.mark.unit
def test_workflow_status_enum() -> None:
    """Test WorkflowStatus enum values."""
    assert WorkflowStatus.RUNNING == "running"
    assert WorkflowStatus.COMPLETED == "completed"
    assert WorkflowStatus.FAILED == "failed"
    assert WorkflowStatus.CANCELLED == "cancelled"
    assert WorkflowStatus.TIMED_OUT == "timed_out"


@pytest.mark.unit
def test_default_constants() -> None:
    """Test default constant values."""
    assert DEFAULT_TIMEOUT_SECONDS == 300
    assert DEFAULT_RETRY_ATTEMPTS == 3
    assert DEFAULT_HTTP_TIMEOUT_SECONDS == 30
    assert DEFAULT_LLM_TEMPERATURE == 0.7
    assert DEFAULT_LLM_MAX_TOKENS == 2048


@pytest.mark.unit
def test_api_paths() -> None:
    """Test API path constants."""
    assert XIANS_API_BASE_PATH == "/api/v1"
    assert XIANS_AGENT_PATH == "/api/v1/agents"
    assert XIANS_WORKFLOW_PATH == "/api/v1/workflows"
    assert XIANS_KNOWLEDGE_PATH == "/api/v1/knowledge"
    assert XIANS_DOCUMENT_PATH == "/api/v1/documents"
    assert XIANS_CONVERSATION_PATH == "/api/v1/conversations"


@pytest.mark.unit
def test_enum_string_comparison() -> None:
    """Test that enum values work with string comparison."""
    provider = LLMProvider.OPENAI

    assert provider == "openai"
    assert provider.value == "openai"
    # str() representation includes the enum class name
    assert "openai" in str(provider).lower()
