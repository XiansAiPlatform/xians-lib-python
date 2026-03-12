"""Configuration models for Xians SDK v1.

Aligned with C# XiansOptions, ServerConfiguration, and TemporalConfiguration.
"""

import os
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator

from ...constants.v1.core import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_RETRY_ATTEMPTS,
    LLMProvider,
)


class CertificateInfo(BaseModel):
    """Parsed X.509 certificate metadata. Matches C# CertificateInfo."""

    tenant_id: str
    user_id: str
    subject: str
    thumbprint: str
    expires_at: datetime


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
        """Compose address from host/port if not provided."""
        address = values.get("address")
        host = values.get("host")
        port = values.get("port")
        if not address and host:
            if port:
                values["address"] = f"{host}:{port}"
            else:
                values["address"] = f"{host}:7233"
        return values

    @model_validator(mode="after")
    def populate_legacy_host_port(self) -> "TemporalConfig":
        """Populate legacy host/port fields from address."""
        try:
            if (self.host is None or self.port is None) and self.address:
                addr = self.address
                if "://" in addr:
                    addr = addr.split("://", 1)[1]
                parts = addr.split(":")
                if len(parts) == 2:
                    self.host = self.host or parts[0]
                    try:
                        self.port = self.port or int(parts[1])
                    except ValueError:
                        self.port = self.port or 7233
                else:
                    self.host = self.host or addr
                    self.port = self.port or 7233
        except Exception:
            pass
        return self

    @model_validator(mode="after")
    def migrate_legacy_tls(self) -> "TemporalConfig":
        """Map legacy TLS fields into nested TemporalTLSConfig."""
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
    """Configuration for LLM provider. DEPRECATED - configure LLM in your activities."""

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
        if isinstance(v, LLMProvider):
            return v
        if isinstance(v, str):
            v_lower = v.strip().lower()
            for member in LLMProvider:
                if member.value.lower() == v_lower:
                    return member
            return LLMProvider(v)
        return v

    @field_validator("api_key", mode="before")
    @classmethod
    def coerce_api_key(cls, v: str | SecretStr | None) -> SecretStr | None:
        if v is None:
            return None
        if isinstance(v, SecretStr):
            return v
        return SecretStr(str(v).strip()) if str(v).strip() else None

    @field_validator("api_base", mode="before")
    @classmethod
    def coerce_api_base(cls, v: str | HttpUrl | None) -> HttpUrl | None:
        if v is None:
            return None
        if isinstance(v, HttpUrl):
            return v
        from pydantic import TypeAdapter
        return TypeAdapter(HttpUrl).validate_python(v)


class XiansServerConfig(BaseModel):
    """Configuration for Xians server connection. Matches C# ServerConfiguration."""

    server_url: str = Field(description="Xians server base URL")
    api_key: str = Field(description="Base64-encoded PFX certificate")
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier (from certificate)")
    timeout_seconds: float = Field(
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        description="Request timeout in seconds",
    )
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    model_config = {"frozen": False, "populate_by_name": True}


class XiansOptions(BaseModel):
    """Main configuration options for XiansPlatform.

    Matches C# XiansOptions : ServerConfiguration.
    The api_key is a Base64-encoded X.509 certificate (PFX) containing
    tenant ID and user ID in the subject fields.
    """

    server_url: str = Field(description="Xians server base URL")
    api_key: str = Field(description="Base64-encoded X.509 certificate (PFX)")
    temporal: TemporalConfig | None = Field(
        default=None,
        description="Temporal configuration (if None, fetched from server)",
    )
    console_log_level: Optional[str] = Field(default=None, description="Console logging level")
    server_log_level: Optional[str] = Field(default=None, description="Server logging level")
    enable_tasks: bool = Field(default=False, description="Enable HITL task workflows")
    local_mode: bool = Field(default=False, description="Local mode (no Temporal)")

    # Keep for backward compat but deprecated
    log_level: str = Field(default="INFO", description="[Deprecated] Use console_log_level")
    enable_structured_logging: bool | str = Field(
        default=False,
        description="Enable structured logging with structlog",
    )

    _certificate_info: Optional[CertificateInfo] = None

    model_config = {"frozen": False, "populate_by_name": True}

    @property
    def certificate_info(self) -> CertificateInfo:
        """Lazily parse certificate from api_key."""
        if self._certificate_info is None:
            from ...utils.v1.certificate import parse_certificate
            cert_data = parse_certificate(self.api_key)
            self._certificate_info = CertificateInfo(**cert_data)
        return self._certificate_info

    @property
    def certificate_tenant_id(self) -> str:
        return self.certificate_info.tenant_id

    @property
    def certificate_user_id(self) -> str:
        return self.certificate_info.user_id

    @classmethod
    def from_env(cls) -> "XiansOptions":
        """Create XiansOptions from environment variables."""
        return cls(
            server_url=os.environ.get("SERVER_URL") or os.environ.get("XIANS_SERVER_URL", ""),
            api_key=os.environ.get("API_KEY") or os.environ.get("XIANS_API_KEY", ""),
            console_log_level=os.environ.get("CONSOLE_LOG_LEVEL"),
            server_log_level=os.environ.get("SERVER_LOG_LEVEL") or os.environ.get("API_LOG_LEVEL"),
        )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return str(v).strip().upper()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @field_validator("enable_structured_logging", mode="before")
    @classmethod
    def coerce_bool(cls, v: bool | str | None) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in {"true", "1", "yes", "y", "on"}


__all__ = [
    "CertificateInfo",
    "TemporalTLSConfig",
    "TemporalConfig",
    "LLMConfig",
    "XiansServerConfig",
    "XiansOptions",
]
