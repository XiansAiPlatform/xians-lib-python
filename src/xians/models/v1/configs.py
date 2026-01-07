from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator

from ...constants.v1.core import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_RETRY_ATTEMPTS,
    LLMProvider,
)


class TemporalConfig(BaseModel):
    """Configuration for Temporal connection."""

    host: str = Field(default="localhost", description="Temporal server host")
    port: int = Field(default=7233, description="Temporal server port", ge=1, le=65535)
    namespace: str = Field(default="default", description="Temporal namespace")
    task_queue: str = Field(default="xians-agents", description="Task queue name")
    tls_enabled: bool = Field(default=False, description="Enable TLS connection")
    tls_cert_path: str | None = Field(default=None, description="Path to TLS certificate")

    model_config = {"frozen": False}


class LLMConfig(BaseModel):
    """Configuration for LLM provider."""

    provider: LLMProvider = Field(description="LLM provider name")
    model: str = Field(description="Model identifier")
    api_key: SecretStr | None = Field(default=None, description="API key for provider")
    api_base: HttpUrl | None = Field(default=None, description="Custom API base URL")
    temperature: float = Field(
        default=DEFAULT_LLM_TEMPERATURE,
        description="Sampling temperature",
        ge=0.0,
        le=2.0,
    )
    max_tokens: int = Field(
        default=DEFAULT_LLM_MAX_TOKENS,
        description="Maximum tokens to generate",
        ge=1,
    )
    timeout_seconds: int = Field(
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        description="Request timeout in seconds",
        ge=1,
    )
    extra_params: dict[str, object] = Field(
        default_factory=dict,
        description="Additional provider-specific parameters",
    )

    model_config = {"frozen": False}


class XiansServerConfig(BaseModel):
    """Configuration for Xians server connection."""

    server_url: HttpUrl = Field(description="Xians server base URL")
    api_key: SecretStr = Field(description="API key for authentication")
    timeout_seconds: int = Field(
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        description="Request timeout in seconds",
        ge=1,
    )
    retry_attempts: int = Field(
        default=DEFAULT_RETRY_ATTEMPTS,
        description="Number of retry attempts",
        ge=0,
    )
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    model_config = {"frozen": False}

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: SecretStr) -> SecretStr:
        """Validate API key to catch common mistakes."""
        key_value = v.get_secret_value().strip()

        if not key_value:
            raise ValueError("API key cannot be empty")

        if len(key_value) < 10:
            raise ValueError("API key appears to be too short (minimum 10 characters)")

        placeholder_patterns = [
            "your-api-key",
            "your_api_key",
            "xxx",
            "placeholder",
            "test",
            "example",
        ]

        key_lower = key_value.lower()
        for pattern in placeholder_patterns:
            if pattern in key_lower:
                raise ValueError(
                    f"API key appears to be a placeholder ('{pattern}' detected). "
                    "Please replace with your actual API key."
                )

        # Return with stripped whitespace
        return SecretStr(key_value)


class XiansOptions(BaseModel):
    """
    Main configuration options for XiansPlatform.

    This is the primary configuration object users provide when initializing the SDK.
    """

    server_url: HttpUrl = Field(description="Xians server base URL")
    api_key: SecretStr = Field(description="API key for authentication")
    temporal: TemporalConfig | None = Field(
        default=None,
        description="Temporal configuration (if None, fetch from server)",
    )
    llm: LLMConfig = Field(description="LLM configuration")
    log_level: str = Field(default="INFO", description="Logging level")
    enable_structured_logging: bool = Field(
        default=False,
        description="Enable structured logging with structlog",
    )

    model_config = {"frozen": False}

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str | SecretStr) -> SecretStr:
        """Validate API key to catch common mistakes."""
        # Handle both plain strings and SecretStr
        if isinstance(v, SecretStr):
            key_value = v.get_secret_value()
        else:
            key_value = str(v) if v is not None else ""

        # Strip whitespace
        key_value = key_value.strip()

        if not key_value:
            raise ValueError("API key cannot be empty")

        if len(key_value) < 10:
            raise ValueError("API key appears to be too short (minimum 10 characters)")

        # Check for common placeholder values (only check first 50 chars to avoid false positives on long tokens)
        check_value = key_value[:50].lower()
        placeholder_patterns = [
            "your-api-key",
            "your_api_key",
            "xxx",
            "placeholder",
            "test-key",
            "example-key",
        ]

        for pattern in placeholder_patterns:
            if pattern in check_value:
                raise ValueError(
                    f"API key appears to be a placeholder ('{pattern}' detected). "
                    "Please replace with your actual API key."
                )

        # Return with stripped whitespace
        return SecretStr(key_value)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


__all__ = [
    "TemporalConfig",
    "LLMConfig",
    "XiansServerConfig",
    "XiansOptions",
]
