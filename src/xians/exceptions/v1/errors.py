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
    "XiansServerError",
    "LLMError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceNotFoundError",
]
