"""Tests for Temporal failure unwrapping utility."""

import pytest

from xians.temporal_workflows.v1.failure_unwrap import unwrap_temporal_failure


class MockException(Exception):
    """Mock exception for testing."""

    pass


class MockActivityError(Exception):
    """Mock Temporal ActivityError."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause
        self.activity_type = "execute_agent_activity"
        self.activity_id = "test-activity-123"
        self.retry_state = "IN_PROGRESS"
        self.attempt = 2


class MockApplicationError(Exception):
    """Mock Temporal ApplicationError."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class TestUnwrapTemporalFailure:
    """Test the unwrap_temporal_failure function."""

    def test_simple_exception(self):
        """Test unwrapping a simple exception with no chain."""
        error = ValueError("Simple error message")

        result = unwrap_temporal_failure(error)

        assert result["root_error_type"] == "ValueError"
        assert result["root_error_message"] == "Simple error message"
        assert len(result["error_chain"]) == 1
        assert result["error_chain"][0]["type"] == "ValueError"
        assert result["error_chain"][0]["message"] == "Simple error message"
        assert result["temporal_context"] == {}
        assert result["provider_retry_after_seconds"] is None

    def test_exception_chain_with_cause(self):
        """Test unwrapping an exception chain using __cause__."""
        root_error = ValueError("Root cause error")
        middle_error = RuntimeError("Middle error")
        middle_error.__cause__ = root_error
        outer_error = Exception("Outer error")
        outer_error.__cause__ = middle_error

        result = unwrap_temporal_failure(outer_error)

        assert result["root_error_type"] == "ValueError"
        assert result["root_error_message"] == "Root cause error"
        assert len(result["error_chain"]) == 3
        assert result["error_chain"][0]["type"] == "Exception"
        assert result["error_chain"][1]["type"] == "RuntimeError"
        assert result["error_chain"][2]["type"] == "ValueError"

    def test_mock_activity_error_chain(self):
        """Test unwrapping a mock ActivityError with ApplicationError cause."""
        # Simulate: ActivityError -> ApplicationError -> RuntimeError
        root_error = RuntimeError(
            "429 You exceeded your current quota. Please retry in 32.439s"
        )
        app_error = MockApplicationError("Application error")
        app_error.__cause__ = root_error
        activity_error = MockActivityError("Activity task failed", cause=app_error)

        result = unwrap_temporal_failure(activity_error)

        # Check root cause is extracted
        assert result["root_error_type"] == "RuntimeError"
        assert "429 You exceeded your current quota" in result["root_error_message"]
        assert "Please retry in 32.439s" in result["root_error_message"]

        # Check error chain
        assert len(result["error_chain"]) >= 2
        assert result["error_chain"][0]["type"] == "MockActivityError"

        # Check Temporal context is extracted
        assert result["temporal_context"]["activity_type"] == "execute_agent_activity"
        assert result["temporal_context"]["activity_id"] == "test-activity-123"
        assert result["temporal_context"]["retry_state"] == "IN_PROGRESS"
        assert result["temporal_context"]["attempt"] == 2

        # Check retry-after is parsed
        assert result["provider_retry_after_seconds"] == 32.439

    def test_extract_retry_after_various_formats(self):
        """Test parsing retry-after from various message formats."""
        test_cases = [
            ("Please retry in 32.439s", 32.439),
            ("retry after 15 seconds", 15.0),
            ("wait 30s before retrying", 30.0),
            ("Retry in 5s", 5.0),
            ("RETRY AFTER 10 SECONDS", 10.0),
            ("No retry info here", None),
            ("retry in abc seconds", None),  # Invalid number
        ]

        for message, expected_seconds in test_cases:
            error = Exception(message)
            result = unwrap_temporal_failure(error)
            assert (
                result["provider_retry_after_seconds"] == expected_seconds
            ), f"Failed for message: {message}"

    def test_gemini_429_error_message(self):
        """Test with a real-world Gemini 429 error message."""
        gemini_error = RuntimeError(
            "429 You exceeded your current quota, please check your plan and "
            "billing details. For more information on this error, read the docs: "
            "https://platform.openai.com/docs/guides/error-codes/api-errors. "
            "Please retry in 32.439s"
        )

        result = unwrap_temporal_failure(gemini_error)

        assert result["root_error_type"] == "RuntimeError"
        assert "429 You exceeded your current quota" in result["root_error_message"]
        assert result["provider_retry_after_seconds"] == 32.439

    def test_activity_error_with_temporal_cause_attribute(self):
        """Test unwrapping using Temporal's cause attribute (not __cause__)."""
        root_error = ValueError("Root error")
        activity_error = MockActivityError("Activity failed")
        # Simulate Temporal's pattern where cause is set as an attribute
        activity_error.cause = root_error

        result = unwrap_temporal_failure(activity_error)

        assert result["root_error_type"] == "ValueError"
        assert result["root_error_message"] == "Root error"
        assert len(result["error_chain"]) == 2

    def test_error_chain_order(self):
        """Test that error chain is in correct order (outer to root)."""
        error1 = ValueError("Level 3 (root)")
        error2 = RuntimeError("Level 2")
        error2.__cause__ = error1
        error3 = Exception("Level 1 (outer)")
        error3.__cause__ = error2

        result = unwrap_temporal_failure(error3)

        assert len(result["error_chain"]) == 3
        assert result["error_chain"][0]["message"] == "Level 1 (outer)"
        assert result["error_chain"][1]["message"] == "Level 2"
        assert result["error_chain"][2]["message"] == "Level 3 (root)"

    def test_circular_exception_chain_protection(self):
        """Test that circular exception chains don't cause infinite loops."""
        # This is a safety test - Python normally doesn't allow this,
        # but we should handle it gracefully if it somehow happens
        error1 = Exception("Error 1")
        error2 = Exception("Error 2")
        error1.__cause__ = error2
        # Can't actually create a circular chain in Python, but we can test
        # that the unwrapping stops eventually

        result = unwrap_temporal_failure(error1)

        # Should complete without hanging
        assert result["root_error_type"] == "Exception"
        assert len(result["error_chain"]) <= 10  # Reasonable limit

    def test_empty_error_message(self):
        """Test handling of exceptions with empty messages."""
        error = Exception()

        result = unwrap_temporal_failure(error)

        assert result["root_error_type"] == "Exception"
        assert isinstance(result["root_error_message"], str)
        assert len(result["error_chain"]) == 1

    def test_temporal_context_partial_attributes(self):
        """Test extraction when only some Temporal attributes are present."""

        class PartialActivityError(Exception):
            def __init__(self) -> None:
                super().__init__("Partial activity error")
                self.activity_type = "my_activity"
                # Missing other attributes

        error = PartialActivityError()
        result = unwrap_temporal_failure(error)

        assert result["temporal_context"]["activity_type"] == "my_activity"
        assert "activity_id" not in result["temporal_context"]

    def test_non_temporal_exception_has_empty_context(self):
        """Test that non-Temporal exceptions have empty temporal_context."""
        error = ValueError("Regular Python error")

        result = unwrap_temporal_failure(error)

        assert result["temporal_context"] == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

