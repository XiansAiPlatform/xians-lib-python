from typing import Any


class XiansError(Exception):

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause


class ConfigurationError(XiansError):
    """Raised when configuration is invalid or incomplete."""


class TemporalError(XiansError):
    """Raised when Temporal workflow/activity operations fail."""


class AgentExecutionError(XiansError):
    """Raised when agent execution fails within a workflow/activity.

    This exception captures detailed failure information from agent execution,
    including the root cause, error chain, and Temporal context.

    Attributes:
        workflow_id: Optional workflow identifier.
        task_queue: Optional task queue name.
        error_details: Structured error details from failure unwrapping.
    """

    def __init__(
        self,
        message: str,
        *,
        workflow_id: str | None = None,
        task_queue: str | None = None,
        error_details: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Merge error_details into details if provided
        merged_details = details or {}
        if error_details:
            merged_details["error_details"] = error_details

        super().__init__(message, details=merged_details, cause=cause)
        self.workflow_id = workflow_id
        self.task_queue = task_queue
        self.error_details = error_details or {}


class XiansServerError(XiansError):
    """Raised when Xians server API calls fail."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        method: str | None = None,
        url: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)
        self.status_code = status_code
        self.response_body = response_body
        self.method = method
        self.url = url


class LLMError(XiansError):
    """Raised when LLM operations fail."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)
        self.provider = provider
        self.model = model


class ValidationError(XiansError):
    """Raised when data validation fails."""


class AuthenticationError(XiansError):
    """Raised when authentication fails."""


class AuthorizationError(XiansError):
    """Raised when authorization/permission checks fail."""


class ResourceNotFoundError(XiansError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)
        self.resource_type = resource_type
        self.resource_id = resource_id


__all__ = [
    "XiansError",
    "ConfigurationError",
    "TemporalError",
    "AgentExecutionError",
    "XiansServerError",
    "LLMError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceNotFoundError",
]
