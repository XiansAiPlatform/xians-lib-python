from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator
from pydantic import FieldValidationInfo, model_validator

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
    server_root_ca_cert_base64: SecretStr | None = Field(
        default=None,
        description="Base64-encoded server root CA certificate",
    )
    client_cert_base64: SecretStr | None = Field(
        default=None,
        description="Base64-encoded client certificate for mTLS",
    )
    client_private_key_base64: SecretStr | None = Field(
        default=None,
        description="Base64-encoded client private key for mTLS",
    )

    model_config = {"frozen": False, "populate_by_name": True}

    @field_validator("client_cert_base64", "client_private_key_base64")
    @classmethod
    def validate_mtls_pairs(
        cls, v: SecretStr | None, info: FieldValidationInfo
    ) -> SecretStr | None:
        """Ensure mTLS cert/key are provided together when either is set."""
        cert = v if v else info.data.get("client_cert_base64")
        key = v if v else info.data.get("client_private_key_base64")
        if cert and not key:
            raise ValueError("client_private_key_base64 must be set when client_cert_base64 is provided")
        if key and not cert:
            raise ValueError("client_cert_base64 must be set when client_private_key_base64 is provided")
        return v


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
    auth_mode: Literal["bearer_cert", "x_api_key"] = Field(
        default="bearer_cert",
        description="Authentication mode for server requests",
    )
    bearer_cert_base64: SecretStr | None = Field(
        default=None,
        description="Base64-encoded certificate used for Bearer auth",
        alias="api_key",
    )
    x_api_key: SecretStr | None = Field(
        default=None,
        description="Legacy X-API-Key value for auth_mode='x_api_key'",
    )
    tenant_id: str | None = Field(default=None, description="Tenant identifier for requests")
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

    model_config = {"frozen": False, "populate_by_name": True}

    @field_validator("bearer_cert_base64", "x_api_key")
    @classmethod
    def validate_auth_value(cls, v: SecretStr | None) -> SecretStr | None:
        """Validate auth secrets to catch common mistakes."""
        if v is None:
            return None
        key_value = v.get_secret_value().strip()
        if not key_value:
            raise ValueError("Authentication secret cannot be empty")
        if len(key_value) < 10:
            raise ValueError("Authentication secret appears too short (minimum 10 characters)")
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
                    f"Authentication secret appears to be a placeholder ('{pattern}' detected). "
                    "Please provide a valid credential."
                )
        return SecretStr(key_value)

    @model_validator(mode="after")
    def validate_auth_mode(self) -> "XiansServerConfig":
        bearer = self.bearer_cert_base64
        x_api = self.x_api_key
        if self.auth_mode == "bearer_cert" and not bearer:
            raise ValueError("bearer_cert auth_mode requires bearer_cert_base64")
        if self.auth_mode == "x_api_key" and not x_api:
            raise ValueError("x_api_key auth_mode requires x_api_key")
        return self


class XiansOptions(BaseModel):
    """
    Main configuration options for XiansPlatform.

    This is the primary configuration object users provide when initializing the SDK.
    """

    server_url: HttpUrl = Field(description="Xians server base URL")
    server_api_key: SecretStr | None = Field(
        description="Base64-encoded certificate used for server authentication",
        alias="api_key",
    )
    server_auth_mode: Literal["bearer_cert", "x_api_key"] = Field(
        default="bearer_cert",
        description="Authentication mode for server requests",
    )
    server_x_api_key: SecretStr | None = Field(
        default=None,
        description="Legacy X-API-Key credential for auth_mode='x_api_key'",
    )
    tenant_id: str | None = Field(default=None, description="Tenant identifier")
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

    model_config = {"frozen": False, "populate_by_name": True}

    @field_validator("server_api_key", mode="before")
    @classmethod
    def validate_server_api_key(cls, v: str | SecretStr | None) -> SecretStr | None:
        """Validate server API key (base64 certificate) to catch common mistakes."""
        if v is None:
            return None
        if isinstance(v, SecretStr):
            key_value = v.get_secret_value()
        else:
            key_value = str(v) if v is not None else ""
        key_value = key_value.strip()
        if not key_value:
            raise ValueError("API key cannot be empty")
        if len(key_value) < 10:
            raise ValueError("API key appears to be too short (minimum 10 characters)")
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
        return SecretStr(key_value)

    @model_validator(mode="after")
    def validate_server_auth_mode(self) -> "XiansOptions":
        if self.server_auth_mode == "bearer_cert" and not self.server_api_key:
            raise ValueError("server_api_key is required when server_auth_mode is 'bearer_cert'")
        if self.server_auth_mode == "x_api_key" and not self.server_x_api_key:
            raise ValueError("server_x_api_key is required when server_auth_mode is 'x_api_key'")
        return self

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
