from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator

from ...constants.v1.core import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_RETRY_ATTEMPTS,
    LLMProvider,
)


class TemporalTLSConfig(BaseModel):
    """TLS configuration for Temporal connections.

    Supports both file-path and PEM-string options, base64 decoding, and SNI override.
    """

    enabled: bool = Field(default=False, description="Enable TLS. Inferred True if any TLS fields are set.")
    root_ca_pem: Optional[str] = Field(default=None, description="Root CA certificate PEM string")
    root_ca_path: Optional[str] = Field(default=None, description="Path to Root CA certificate PEM file")
    client_cert_pem: Optional[str] = Field(default=None, description="Client certificate PEM string for mTLS")
    client_cert_path: Optional[str] = Field(default=None, description="Path to client certificate PEM file for mTLS")
    client_key_pem: Optional[str] = Field(default=None, description="Client private key PEM string for mTLS")
    client_key_path: Optional[str] = Field(default=None, description="Path to client private key PEM file for mTLS")
    domain: Optional[str] = Field(default=None, description="SNI override: server name/certificate hostname")
    pem_is_base64: bool = Field(default=False, description="Decode provided *_pem fields from base64 before use")

    model_config = {"frozen": False, "populate_by_name": True}

    @model_validator(mode="after")
    def validate_tls_enabled_and_pairs(self) -> "TemporalTLSConfig":
        """Infer enabled flag and validate mTLS pairs."""
        any_material = any(
            [
                self.root_ca_pem,
                self.root_ca_path,
                self.client_cert_pem,
                self.client_cert_path,
                self.client_key_pem,
                self.client_key_path,
            ]
        )
        if any_material:
            self.enabled = True
        # mTLS pair validation
        has_cert = bool(self.client_cert_pem or self.client_cert_path)
        has_key = bool(self.client_key_pem or self.client_key_path)
        if has_cert != has_key:
            raise ValueError(
                "mTLS requires both client cert and private key. Provide client_cert_* and client_key_*."
            )
        return self


class TemporalConfig(BaseModel):
    """Configuration for Temporal connection."""

    address: str = Field(default="localhost:7233", description="Temporal server address 'host:port'")
    namespace: str = Field(default="default", description="Temporal namespace")
    task_queue: str = Field(default="xians-agents", description="Task queue name")
    tls: TemporalTLSConfig | None = Field(default=None, description="TLS configuration for Temporal")

    # Backward compatibility fields (deprecated): host/port/tls_*; allow populate_by_name
    host: str | None = Field(default=None, description="[Deprecated] Temporal server host")
    port: int | None = Field(default=None, description="[Deprecated] Temporal server port", ge=1, le=65535)
    tls_enabled: bool = Field(default=False, description="[Deprecated] Use tls.enabled")
    tls_cert_path: str | None = Field(default=None, description="[Deprecated] Use tls.root_ca_path")
    server_root_ca_cert_base64: SecretStr | None = Field(default=None, description="[Deprecated]")
    client_cert_base64: SecretStr | None = Field(default=None, description="[Deprecated]")
    client_private_key_base64: SecretStr | None = Field(default=None, description="[Deprecated]")

    model_config = {"frozen": False, "populate_by_name": True}

    @model_validator(mode="before")
    def compose_address(cls, values: dict) -> dict:
        """Compose address from host/port if not provided to keep backward compatibility."""
        address = values.get("address")
        host = values.get("host")
        port = values.get("port")
        if not address and host:
            if port:
                values["address"] = f"{host}:{port}"
            else:
                # Default Temporal port 7233 if not provided
                values["address"] = f"{host}:7233"
        return values

    @model_validator(mode="after")
    def populate_legacy_host_port(self) -> "TemporalConfig":
        """Populate legacy host/port fields from address if missing to satisfy backward compatibility tests."""
        try:
            if (self.host is None or self.port is None) and self.address:
                # Parse address into host and port
                addr = self.address
                # Remove scheme if any (not expected but defensive)
                if "://" in addr:
                    addr = addr.split("://", 1)[1]
                parts = addr.split(":")
                if len(parts) == 2:
                    self.host = self.host or parts[0]
                    try:
                        self.port = self.port or int(parts[1])
                    except ValueError:
                        # If port not int, default to 7233
                        self.port = self.port or 7233
                else:
                    # No explicit port; default
                    self.host = self.host or addr
                    self.port = self.port or 7233
        except Exception:
            # Do not raise; keep fields as-is
            pass
        return self

    @model_validator(mode="after")
    def migrate_legacy_tls(self) -> "TemporalConfig":
        """Map legacy TLS fields into nested TemporalTLSConfig when needed."""
        if self.tls is None:
            any_legacy = any(
                [
                    self.tls_enabled,
                    self.tls_cert_path,
                    self.server_root_ca_cert_base64,
                    self.client_cert_base64,
                    self.client_private_key_base64,
                ]
            )
            if any_legacy:
                tls = TemporalTLSConfig()
                tls.enabled = bool(self.tls_enabled)
                if self.tls_cert_path:
                    tls.root_ca_path = self.tls_cert_path
                if self.server_root_ca_cert_base64:
                    tls.root_ca_pem = self.server_root_ca_cert_base64.get_secret_value()
                    tls.pem_is_base64 = True
                if self.client_cert_base64:
                    tls.client_cert_pem = self.client_cert_base64.get_secret_value()
                    tls.pem_is_base64 = True
                if self.client_private_key_base64:
                    tls.client_key_pem = self.client_private_key_base64.get_secret_value()
                    tls.pem_is_base64 = True
                self.tls = tls
        return self


class LLMConfig(BaseModel):
    """Configuration for LLM provider."""

    provider: str | LLMProvider = Field(description="LLM provider name")
    model: str = Field(description="Model identifier")
    api_key: str | SecretStr | None = Field(default=None, description="API key for provider")
    api_base: str | HttpUrl | None = Field(default=None, description="Custom API base URL")
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

    @field_validator("provider", mode="before")
    @classmethod
    def coerce_provider(cls, v: str | LLMProvider) -> LLMProvider:
        """Convert string to LLMProvider enum."""
        if isinstance(v, LLMProvider):
            return v
        if isinstance(v, str):
            # Try to match by value (case-insensitive)
            v_lower = v.strip().lower()
            for member in LLMProvider:
                if member.value.lower() == v_lower:
                    return member
            # If no match, let Pydantic handle the error
            return LLMProvider(v)
        return v

    @field_validator("api_key", mode="before")
    @classmethod
    def coerce_api_key(cls, v: str | SecretStr | None) -> SecretStr | None:
        """Convert plain string to SecretStr."""
        if v is None:
            return None
        if isinstance(v, SecretStr):
            return v
        return SecretStr(str(v).strip()) if str(v).strip() else None

    @field_validator("api_base", mode="before")
    @classmethod
    def coerce_api_base(cls, v: str | HttpUrl | None) -> HttpUrl | None:
        """Convert plain string to HttpUrl."""
        if v is None:
            return None
        if isinstance(v, HttpUrl):
            return v
        # Convert string to HttpUrl (Pydantic will handle validation)
        from pydantic import TypeAdapter
        return TypeAdapter(HttpUrl).validate_python(v)


class XiansServerConfig(BaseModel):
    """Configuration for Xians server connection."""

    server_url: str | HttpUrl = Field(description="Xians server base URL")
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

    @field_validator("server_url", mode="before")
    @classmethod
    def coerce_server_url(cls, v: str | HttpUrl) -> HttpUrl:
        """Allow plain string URLs to be converted to HttpUrl."""
        if isinstance(v, HttpUrl):
            return v
        # Convert string to HttpUrl (Pydantic will handle validation)
        from pydantic import TypeAdapter
        return TypeAdapter(HttpUrl).validate_python(v)

    @field_validator("bearer_cert_base64", "x_api_key", mode="before")
    @classmethod
    def coerce_secret_str_fields(cls, v: str | SecretStr | None) -> SecretStr | None:
        """Convert plain strings to SecretStr."""
        if v is None:
            return None
        if isinstance(v, SecretStr):
            return v
        return SecretStr(str(v).strip()) if str(v).strip() else None

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

    server_url: str | HttpUrl = Field(description="Xians server base URL")
    server_api_key: str | SecretStr | None = Field(
        default=None,
        description="Base64-encoded certificate used for server authentication",
        alias="api_key",
    )
    server_auth_mode: Literal["bearer_cert", "x_api_key"] = Field(
        default="bearer_cert",
        description="Authentication mode for server requests",
    )
    server_x_api_key: str | SecretStr | None = Field(
        default=None,
        description="Legacy X-API-Key credential for auth_mode='x_api_key'",
    )
    tenant_id: str | None = Field(default=None, description="Tenant identifier")
    temporal: TemporalConfig | None = Field(
        default=None,
        description="Temporal configuration (if None, fetch from server)",
    )
    llm: LLMConfig | dict = Field(description="LLM configuration")
    log_level: str = Field(default="INFO", description="Logging level")
    enable_structured_logging: bool | str = Field(
        default=False,
        description="Enable structured logging with structlog",
    )

    model_config = {"frozen": False, "populate_by_name": True}

    @field_validator("server_url", mode="before")
    @classmethod
    def coerce_server_url(cls, v: str | HttpUrl) -> HttpUrl:
        """Allow plain string URLs to be converted to HttpUrl."""
        if isinstance(v, HttpUrl):
            return v
        # Convert string to HttpUrl (Pydantic will handle validation)
        from pydantic import TypeAdapter
        return TypeAdapter(HttpUrl).validate_python(v)

    # Coerce auth mode from string (case-insensitive)
    @field_validator("server_auth_mode", mode="before")
    @classmethod
    def normalize_auth_mode(cls, v: str | Literal["bearer_cert", "x_api_key"]) -> str:
        if isinstance(v, str):
            val = v.strip().lower().replace("-", "_")
            if val in {"bearer_cert", "x_api_key"}:
                return val
        return v

    # Convert and validate server_api_key
    @field_validator("server_api_key", mode="before")
    @classmethod
    def validate_server_api_key(cls, v: str | SecretStr | None) -> SecretStr | None:
        """Convert and validate server API key (base64 certificate) to catch common mistakes."""
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

    # Convert server_x_api_key from plain strings to SecretStr
    @field_validator("server_x_api_key", mode="before")
    @classmethod
    def coerce_server_x_api_key(cls, v: str | SecretStr | None) -> SecretStr | None:
        if v is None:
            return None
        if isinstance(v, SecretStr):
            return v
        s = str(v).strip()
        return SecretStr(s) if s else None

    # Coerce enable_structured_logging from string to bool
    @field_validator("enable_structured_logging", mode="before")
    @classmethod
    def coerce_bool(cls, v: bool | str | None) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        truthy = {"true", "1", "yes", "y", "on"}
        falsy = {"false", "0", "no", "n", "off"}
        if s in truthy:
            return True
        if s in falsy:
            return False
        # default to False for unknown strings
        return False

    @model_validator(mode="after")
    def validate_server_auth_mode(self) -> "XiansOptions":
        if self.server_auth_mode == "bearer_cert" and not self.server_api_key:
            raise ValueError("server_api_key is required when server_auth_mode is 'bearer_cert'")
        if self.server_auth_mode == "x_api_key" and not self.server_x_api_key:
            raise ValueError("server_x_api_key is required when server_auth_mode is 'x_api_key'")
        return self

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return str(v).strip().upper()

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
    "TemporalTLSConfig",
    "TemporalConfig",
    "LLMConfig",
    "XiansServerConfig",
    "XiansOptions",
]
