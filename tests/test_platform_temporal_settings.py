"""Tests for Temporal settings parsing from Xians server."""

import os
from unittest import mock

import pytest

from xians.exceptions.v1.errors import ConfigurationError
from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import TemporalConfig


@pytest.mark.unit
def test_build_temporal_config_from_settings_parses_net_fields() -> None:
    """Ensure .NET-shaped payload is parsed into TemporalConfig with TLS fields."""
    settings = {
        "flowServerUrl": "temporal.company.com:7234",
        "flowServerNamespace": "prod",
        "flowServerCertBase64": "Y2VydC1kYXRh",
        "flowServerPrivateKeyBase64": "cHJpdmF0ZS1rZXk=",
    }

    cfg = XiansPlatform._build_temporal_config_from_settings(settings)

    assert isinstance(cfg, TemporalConfig)
    assert cfg.host == "temporal.company.com"
    assert cfg.port == 7234
    assert cfg.namespace == "prod"
    assert cfg.tls_enabled is True
    assert cfg.server_root_ca_cert_base64.get_secret_value() == "Y2VydC1kYXRh"
    assert cfg.client_cert_base64.get_secret_value() == "Y2VydC1kYXRh"
    assert cfg.client_private_key_base64.get_secret_value() == "cHJpdmF0ZS1rZXk="


@pytest.mark.unit
def test_build_temporal_config_from_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """TEMPORAL_SERVER_URL overrides flowServerUrl when present."""
    settings = {
        "flowServerUrl": "ignored:1234",
        "flowServerNamespace": "default",
    }

    with mock.patch.dict(os.environ, {"TEMPORAL_SERVER_URL": "custom.host:9000"}):
        cfg = XiansPlatform._build_temporal_config_from_settings(settings)

    assert cfg.host == "custom.host"
    assert cfg.port == 9000


@pytest.mark.unit
def test_build_temporal_config_missing_url_raises() -> None:
    """Missing flowServerUrl should raise ConfigurationError."""
    with pytest.raises(ConfigurationError):
        XiansPlatform._build_temporal_config_from_settings({})
