"""
Unit tests for Pydantic models.
"""

import pytest
from pydantic import SecretStr, ValidationError

from xians.constants.v1.core import LLMProvider, MessageRole, WorkflowType
from xians.models.v1.configs import LLMConfig, TemporalConfig, XiansOptions
from xians.models.v1.entities import (
    AgentDefinition,
    LLMMessage,
    LLMResponse,
    WorkflowDefinition,
)


@pytest.mark.unit
def test_temporal_config_defaults() -> None:
    """Test TemporalConfig with default values."""
    config = TemporalConfig()

    assert config.host == "localhost"
    assert config.port == 7233
    assert config.namespace == "default"
    assert config.task_queue == "xians-agents"
    assert config.tls_enabled is False


@pytest.mark.unit
def test_temporal_config_custom() -> None:
    """Test TemporalConfig with custom values."""
    config = TemporalConfig(
        host="temporal.example.com",
        port=7234,
        namespace="production",
        task_queue="my-queue",
        tls_enabled=True,
    )

    assert config.host == "temporal.example.com"
    assert config.port == 7234
    assert config.namespace == "production"
    assert config.tls_enabled is True


@pytest.mark.unit
def test_temporal_config_invalid_port() -> None:
    """Test TemporalConfig rejects invalid port."""
    with pytest.raises(ValidationError) as exc_info:
        TemporalConfig(port=99999)

    assert "less_than_equal" in str(exc_info.value)


@pytest.mark.unit
def test_llm_config_required_fields() -> None:
    """Test LLMConfig requires provider and model."""
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
    )

    assert config.provider == LLMProvider.OPENAI
    assert config.model == "gpt-4"
    assert config.temperature == 0.7  # default
    assert config.max_tokens == 2048  # default


@pytest.mark.unit
def test_llm_config_with_api_key() -> None:
    """Test LLMConfig with API key."""
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
        api_key=SecretStr("sk-test123"),
    )

    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "sk-test123"


@pytest.mark.unit
def test_llm_config_temperature_validation() -> None:
    """Test LLMConfig validates temperature range."""
    # Valid temperature
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
        temperature=1.5,
    )
    assert config.temperature == 1.5

    # Invalid temperature (too high)
    with pytest.raises(ValidationError):
        LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            temperature=3.0,
        )


@pytest.mark.unit
def test_xians_options_valid(sample_llm_config: LLMConfig) -> None:
    """Test XiansOptions with valid data."""
    options = XiansOptions(
        server_url="https://api.xians.ai",
        api_key=SecretStr("xians-key"),
        llm=sample_llm_config,
    )

    assert str(options.server_url) == "https://api.xians.ai/"
    assert options.api_key.get_secret_value() == "xians-key"
    assert options.log_level == "INFO"  # default


@pytest.mark.unit
def test_xians_options_log_level_validation() -> None:
    """Test XiansOptions validates log level."""
    # Valid log level
    options = XiansOptions(
        server_url="https://api.xians.ai",
        api_key=SecretStr("key"),
        llm=LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4"),
        log_level="debug",  # lowercase
    )
    assert options.log_level == "DEBUG"  # converted to uppercase

    # Invalid log level
    with pytest.raises(ValidationError) as exc_info:
        XiansOptions(
            server_url="https://api.xians.ai",
            api_key=SecretStr("key"),
            llm=LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4"),
            log_level="INVALID",
        )
    assert "log_level must be one of" in str(exc_info.value)


@pytest.mark.unit
def test_llm_message() -> None:
    """Test LLMMessage model."""
    message = LLMMessage(
        role=MessageRole.USER,
        content="Hello, world!",
    )

    assert message.role == MessageRole.USER
    assert message.content == "Hello, world!"
    assert message.name is None


@pytest.mark.unit
def test_llm_response() -> None:
    """Test LLMResponse model."""
    response = LLMResponse(
        text="Hello! How can I help?",
        model="gpt-4",
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    )

    assert response.text == "Hello! How can I help?"
    assert response.model == "gpt-4"
    assert response.usage["total_tokens"] == 30


@pytest.mark.unit
def test_agent_definition() -> None:
    """Test AgentDefinition model."""
    agent = AgentDefinition(
        name="Test Agent",
        description="A test agent",
        system_scoped=True,
        metadata={"version": "1.0"},
    )

    assert agent.name == "Test Agent"
    assert agent.system_scoped is True
    assert agent.metadata["version"] == "1.0"


@pytest.mark.unit
def test_agent_definition_requires_name() -> None:
    """Test AgentDefinition requires a non-empty name."""
    with pytest.raises(ValidationError):
        AgentDefinition(name="")


@pytest.mark.unit
def test_workflow_definition() -> None:
    """Test WorkflowDefinition model."""
    workflow = WorkflowDefinition(
        workflow_type=WorkflowType.CONVERSATIONAL,
        name="Chat Workflow",
        workers=2,
    )

    assert workflow.workflow_type == WorkflowType.CONVERSATIONAL
    assert workflow.name == "Chat Workflow"
    assert workflow.workers == 2


@pytest.mark.unit
def test_workflow_definition_workers_validation() -> None:
    """Test WorkflowDefinition validates workers count."""
    with pytest.raises(ValidationError):
        WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="Test",
            workers=0,  # Must be >= 1
        )
