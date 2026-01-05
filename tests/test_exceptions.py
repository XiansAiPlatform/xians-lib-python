"""
Unit tests for exception classes.
"""

import pytest

from src.exceptions.v1 import (
    AuthenticationError,
    ConfigurationError,
    LLMError,
    ResourceNotFoundError,
    XiansError,
    XiansServerError,
)


@pytest.mark.unit
def test_base_xians_error() -> None:
    """Test XiansError base exception."""
    error = XiansError("Test error", details={"key": "value"})

    assert str(error) == "Test error"
    assert error.message == "Test error"
    assert error.details == {"key": "value"}
    assert error.cause is None


@pytest.mark.unit
def test_xians_error_with_cause() -> None:
    """Test XiansError with a cause exception."""
    cause = ValueError("Original error")
    error = XiansError("Wrapper error", cause=cause)

    assert error.cause is cause
    assert error.message == "Wrapper error"


@pytest.mark.unit
def test_configuration_error() -> None:
    """Test ConfigurationError."""
    error = ConfigurationError("Invalid config", details={"field": "api_key"})

    assert isinstance(error, XiansError)
    assert error.message == "Invalid config"
    assert error.details["field"] == "api_key"


@pytest.mark.unit
def test_xians_server_error() -> None:
    """Test XiansServerError with HTTP details."""
    error = XiansServerError(
        "Server request failed",
        status_code=500,
        response_body='{"error": "Internal error"}',
        details={"endpoint": "/api/v1/agents"},
    )

    assert isinstance(error, XiansError)
    assert error.status_code == 500
    assert error.response_body is not None
    assert "Internal error" in error.response_body
    assert error.details["endpoint"] == "/api/v1/agents"


@pytest.mark.unit
def test_llm_error() -> None:
    """Test LLMError with provider details."""
    error = LLMError(
        "LLM request failed",
        provider="openai",
        model="gpt-4",
        details={"tokens": 1000},
    )

    assert isinstance(error, XiansError)
    assert error.provider == "openai"
    assert error.model == "gpt-4"
    assert error.details["tokens"] == 1000


@pytest.mark.unit
def test_resource_not_found_error() -> None:
    """Test ResourceNotFoundError with resource details."""
    error = ResourceNotFoundError(
        "Agent not found",
        resource_type="agent",
        resource_id="agent-123",
    )

    assert isinstance(error, XiansError)
    assert error.resource_type == "agent"
    assert error.resource_id == "agent-123"


@pytest.mark.unit
def test_authentication_error() -> None:
    """Test AuthenticationError."""
    error = AuthenticationError("Invalid API key")

    assert isinstance(error, XiansError)
    assert error.message == "Invalid API key"
