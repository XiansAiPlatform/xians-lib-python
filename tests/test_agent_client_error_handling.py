"""Tests for AgentClient error handling improvements."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from xians.exceptions.v1.errors import AgentExecutionError, TemporalError
from xians.interfaces.v1.agent_client import AgentClient
from xians.models.v1.entities import AgentRequest, AgentResponse


@pytest.fixture
def mock_temporal_client():
    """Create a mock Temporal client."""
    client = Mock()
    client.start_workflow = AsyncMock()
    client.get_workflow_handle = Mock()
    return client


@pytest.fixture
def agent_client(mock_temporal_client):
    """Create an AgentClient with mock Temporal client."""
    return AgentClient(mock_temporal_client)


@pytest.fixture
def sample_request():
    """Create a sample AgentRequest."""
    return AgentRequest(
        agent_key="test-agent",
        conversation_id="test-conv-123",
        message="Hello, agent!",
    )


class TestAgentClientErrorDetection:
    """Test error detection in AgentClient."""

    def test_is_error_response_with_is_error_flag(self, agent_client):
        """Test detecting error response via is_error flag."""
        error_response = AgentResponse(
            text="Error occurred",
            metadata={"is_error": True, "error": "Something went wrong"},
        )

        assert agent_client._is_error_response(error_response) is True

    def test_is_error_response_with_error_key(self, agent_client):
        """Test detecting error response via error key in metadata."""
        error_response = AgentResponse(
            text="Error occurred",
            metadata={"error": "Something went wrong"},
        )

        assert agent_client._is_error_response(error_response) is True

    def test_is_error_response_success(self, agent_client):
        """Test detecting successful response (no error markers)."""
        success_response = AgentResponse(
            text="Success!",
            metadata={"result": "completed"},
        )

        assert agent_client._is_error_response(success_response) is False

    def test_is_error_response_empty_metadata(self, agent_client):
        """Test detecting response with empty metadata as success."""
        response = AgentResponse(text="Response", metadata={})

        assert agent_client._is_error_response(response) is False


class TestAgentClientInvokeErrorHandling:
    """Test invoke method error handling."""

    @pytest.mark.asyncio
    async def test_invoke_success_logs_correctly(
        self, agent_client, mock_temporal_client, sample_request
    ):
        """Test that successful invoke logs success message."""
        success_response = AgentResponse(
            text="Agent completed successfully",
            metadata={"result": "success"},
        )

        mock_handle = AsyncMock()
        mock_handle.result = AsyncMock(return_value=success_response)
        mock_temporal_client.start_workflow.return_value = mock_handle

        with patch("xians.interfaces.v1.agent_client.logger") as mock_logger:
            result = await agent_client.invoke(
                workflow_id="test-wf-123",
                task_queue="test-queue",
                request=sample_request,
            )

            # Should log success
            mock_logger.info.assert_any_call("Workflow test-wf-123 completed successfully")
            assert result == success_response

    @pytest.mark.asyncio
    async def test_invoke_error_response_logs_error(
        self, agent_client, mock_temporal_client, sample_request
    ):
        """Test that error response logs error message."""
        error_response = AgentResponse(
            text="Agent execution failed (RuntimeError): 429 quota exceeded",
            metadata={
                "is_error": True,
                "error": "429 You exceeded your current quota. Please retry in 32.439s",
                "error_type": "RuntimeError",
                "error_details": {
                    "root_error_type": "RuntimeError",
                    "root_error_message": "429 You exceeded your current quota. Please retry in 32.439s",
                    "provider_retry_after_seconds": 32.439,
                },
            },
        )

        mock_handle = AsyncMock()
        mock_handle.result = AsyncMock(return_value=error_response)
        mock_temporal_client.start_workflow.return_value = mock_handle

        with patch("xians.interfaces.v1.agent_client.logger") as mock_logger:
            result = await agent_client.invoke(
                workflow_id="test-wf-123",
                task_queue="test-queue",
                request=sample_request,
                raise_on_agent_error=False,
            )

            # Should log error with retry info
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "agent error" in error_call
            assert "429 You exceeded your current quota" in error_call
            assert "retry after 32.439s" in error_call

            # Should still return the response
            assert result == error_response

    @pytest.mark.asyncio
    async def test_invoke_raises_on_agent_error_when_flag_set(
        self, agent_client, mock_temporal_client, sample_request
    ):
        """Test that raise_on_agent_error=True raises AgentExecutionError."""
        error_response = AgentResponse(
            text="Agent execution failed",
            metadata={
                "is_error": True,
                "error": "429 quota exceeded",
                "error_details": {
                    "root_error_type": "RuntimeError",
                    "root_error_message": "429 quota exceeded",
                },
            },
        )

        mock_handle = AsyncMock()
        mock_handle.result = AsyncMock(return_value=error_response)
        mock_temporal_client.start_workflow.return_value = mock_handle

        with pytest.raises(AgentExecutionError) as exc_info:
            await agent_client.invoke(
                workflow_id="test-wf-123",
                task_queue="test-queue",
                request=sample_request,
                raise_on_agent_error=True,
            )

        # Check exception details
        assert "429 quota exceeded" in str(exc_info.value)
        assert exc_info.value.workflow_id == "test-wf-123"
        assert exc_info.value.task_queue == "test-queue"
        assert exc_info.value.error_details["root_error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_invoke_workflow_failure_raises_temporal_error(
        self, agent_client, mock_temporal_client, sample_request
    ):
        """Test that workflow start failures raise TemporalError."""
        mock_temporal_client.start_workflow.side_effect = Exception("Connection failed")

        with pytest.raises(TemporalError) as exc_info:
            await agent_client.invoke(
                workflow_id="test-wf-123",
                task_queue="test-queue",
                request=sample_request,
            )

        assert "Failed to invoke workflow test-wf-123" in str(exc_info.value)
        assert exc_info.value.cause is not None


class TestAgentClientInvokeOrRaise:
    """Test invoke_or_raise convenience method."""

    @pytest.mark.asyncio
    async def test_invoke_or_raise_success(
        self, agent_client, mock_temporal_client, sample_request
    ):
        """Test invoke_or_raise returns response on success."""
        success_response = AgentResponse(
            text="Success",
            metadata={"result": "completed"},
        )

        mock_handle = AsyncMock()
        mock_handle.result = AsyncMock(return_value=success_response)
        mock_temporal_client.start_workflow.return_value = mock_handle

        result = await agent_client.invoke_or_raise(
            workflow_id="test-wf-123",
            task_queue="test-queue",
            request=sample_request,
        )

        assert result == success_response

    @pytest.mark.asyncio
    async def test_invoke_or_raise_raises_on_error_response(
        self, agent_client, mock_temporal_client, sample_request
    ):
        """Test invoke_or_raise raises AgentExecutionError on error response."""
        error_response = AgentResponse(
            text="Error",
            metadata={
                "is_error": True,
                "error": "Test error message",
                "error_details": {"root_error_type": "ValueError"},
            },
        )

        mock_handle = AsyncMock()
        mock_handle.result = AsyncMock(return_value=error_response)
        mock_temporal_client.start_workflow.return_value = mock_handle

        with pytest.raises(AgentExecutionError) as exc_info:
            await agent_client.invoke_or_raise(
                workflow_id="test-wf-123",
                task_queue="test-queue",
                request=sample_request,
            )

        assert "Test error message" in str(exc_info.value)


class TestAgentExecutionErrorDetails:
    """Test AgentExecutionError exception class."""

    def test_agent_execution_error_with_full_details(self):
        """Test creating AgentExecutionError with all details."""
        error_details = {
            "root_error_type": "RuntimeError",
            "root_error_message": "429 quota exceeded",
            "provider_retry_after_seconds": 30.0,
        }

        error = AgentExecutionError(
            "Agent failed",
            workflow_id="wf-123",
            task_queue="queue-1",
            error_details=error_details,
        )

        assert str(error) == "Agent failed"
        assert error.workflow_id == "wf-123"
        assert error.task_queue == "queue-1"
        assert error.error_details == error_details
        assert error.details["error_details"] == error_details

    def test_agent_execution_error_minimal(self):
        """Test creating AgentExecutionError with minimal details."""
        error = AgentExecutionError("Simple error")

        assert str(error) == "Simple error"
        assert error.workflow_id is None
        assert error.task_queue is None
        assert error.error_details == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

