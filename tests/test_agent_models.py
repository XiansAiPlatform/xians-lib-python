"""Tests for core agent models (AgentRequest, AgentResponse)."""

from datetime import datetime

import pytest

from src.models.v1.entities import AgentRequest, AgentResponse


class TestAgentRequest:
    """Test suite for AgentRequest model."""

    def test_agent_request_minimal(self) -> None:
        """Test creating AgentRequest with minimal required fields."""
        request = AgentRequest(
            agent_key="test-agent",
            message="Hello, agent!",
        )

        assert request.agent_key == "test-agent"
        assert request.message == "Hello, agent!"
        assert request.conversation_id is None
        assert request.metadata == {}
        assert request.tenant_id is None
        assert request.system_scoped is False
        assert request.idempotency_key is None
        assert isinstance(request.timestamp, datetime)

    def test_agent_request_full(self) -> None:
        """Test creating AgentRequest with all fields."""
        timestamp = datetime.now().astimezone()
        request = AgentRequest(
            agent_key="test-agent",
            conversation_id="conv-123",
            message={"text": "Hello", "metadata": {"source": "test"}},
            metadata={"user_id": "user-456"},
            tenant_id="tenant-789",
            system_scoped=True,
            idempotency_key="idempotent-key",
            timestamp=timestamp,
        )

        assert request.agent_key == "test-agent"
        assert request.conversation_id == "conv-123"
        assert isinstance(request.message, dict)
        assert request.message["text"] == "Hello"
        assert request.metadata["user_id"] == "user-456"
        assert request.tenant_id == "tenant-789"
        assert request.system_scoped is True
        assert request.idempotency_key == "idempotent-key"
        assert request.timestamp == timestamp

    def test_agent_request_empty_agent_key_fails(self) -> None:
        """Test that empty agent key raises validation error."""
        with pytest.raises(ValueError, match="Agent key cannot be empty"):
            AgentRequest(agent_key="   ", message="test")

    def test_agent_request_serialization(self) -> None:
        """Test AgentRequest JSON serialization."""
        request = AgentRequest(
            agent_key="test-agent",
            message="Hello",
            metadata={"key": "value"},
        )

        json_data = request.model_dump(mode="json")
        assert json_data["agent_key"] == "test-agent"
        assert json_data["message"] == "Hello"
        assert "timestamp" in json_data


class TestAgentResponse:
    """Test suite for AgentResponse model."""

    def test_agent_response_text_only(self) -> None:
        """Test creating AgentResponse with text only."""
        response = AgentResponse(text="Hello, user!")

        assert response.text == "Hello, user!"
        assert response.payload is None
        assert response.raw is None
        assert response.usage is None
        assert response.model is None
        assert response.metadata == {}

    def test_agent_response_full(self) -> None:
        """Test creating AgentResponse with all fields."""
        response = AgentResponse(
            text="Hello, user!",
            payload={"result": "success", "data": [1, 2, 3]},
            raw={"provider_response": "raw_data"},
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            model="gpt-4",
            metadata={"latency_ms": 150},
        )

        assert response.text == "Hello, user!"
        assert response.payload["result"] == "success"
        assert response.raw["provider_response"] == "raw_data"
        assert response.usage["prompt_tokens"] == 10
        assert response.model == "gpt-4"
        assert response.metadata["latency_ms"] == 150

    def test_agent_response_payload_only(self) -> None:
        """Test creating AgentResponse with payload but no text."""
        response = AgentResponse(
            payload={"status": "completed", "results": ["item1", "item2"]},
        )

        assert response.text is None
        assert response.payload["status"] == "completed"
        assert len(response.payload["results"]) == 2

    def test_agent_response_serialization(self) -> None:
        """Test AgentResponse JSON serialization."""
        response = AgentResponse(
            text="Response text",
            usage={"tokens": 100},
            model="test-model",
        )

        json_data = response.model_dump(mode="json")
        assert json_data["text"] == "Response text"
        assert json_data["usage"]["tokens"] == 100
        assert json_data["model"] == "test-model"
        assert json_data["metadata"] == {}

