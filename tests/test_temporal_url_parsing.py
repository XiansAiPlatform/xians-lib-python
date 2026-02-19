"""Test Temporal URL parsing logic."""

import pytest
from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import TemporalConfig


class TestTemporalURLParsing:
    """Test URL parsing for Temporal connections."""

    def test_parse_simple_hostname_with_port(self):
        """Test parsing hostname:port format."""
        settings = {
            "flowServerUrl": "agentri-default.ozqzb.tmprl.cloud:7233",
            "flowServerNamespace": "agentri-default.ozqzb",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "agentri-default.ozqzb.tmprl.cloud:7233"
        assert config.namespace == "agentri-default.ozqzb"
        assert config.host == "agentri-default.ozqzb.tmprl.cloud"
        assert config.port == 7233

    def test_parse_hostname_without_port(self):
        """Test parsing hostname without port (defaults to 7233)."""
        settings = {
            "flowServerUrl": "localhost",
            "flowServerNamespace": "default",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "localhost:7233"
        assert config.namespace == "default"
        assert config.host == "localhost"
        assert config.port == 7233

    def test_parse_url_with_dns_scheme(self):
        """Test parsing URL with dns:// scheme prefix."""
        settings = {
            "flowServerUrl": "dns://agentri-default.ozqzb.tmprl.cloud:7233",
            "flowServerNamespace": "agentri-default.ozqzb",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "agentri-default.ozqzb.tmprl.cloud:7233"
        assert config.host == "agentri-default.ozqzb.tmprl.cloud"
        assert config.port == 7233

    def test_parse_url_with_https_scheme(self):
        """Test parsing URL with https:// scheme prefix."""
        settings = {
            "flowServerUrl": "https://temporal.example.com:7233",
            "flowServerNamespace": "production",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "temporal.example.com:7233"
        assert config.host == "temporal.example.com"
        assert config.port == 7233

    def test_parse_url_with_trailing_slash(self):
        """Test parsing URL with trailing slash."""
        settings = {
            "flowServerUrl": "temporal.example.com:7233/",
            "flowServerNamespace": "default",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "temporal.example.com:7233"
        assert config.host == "temporal.example.com"
        assert config.port == 7233

    def test_parse_url_with_whitespace(self):
        """Test parsing URL with leading/trailing whitespace."""
        settings = {
            "flowServerUrl": "  temporal.example.com:7233  ",
            "flowServerNamespace": "default",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "temporal.example.com:7233"
        assert config.host == "temporal.example.com"
        assert config.port == 7233

    def test_parse_invalid_port(self):
        """Test parsing URL with invalid port (defaults to 7233)."""
        settings = {
            "flowServerUrl": "temporal.example.com:invalid",
            "flowServerNamespace": "default",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "temporal.example.com:7233"
        assert config.host == "temporal.example.com"
        assert config.port == 7233

    def test_parse_with_tls_config(self):
        """Test parsing URL with TLS configuration."""
        settings = {
            "flowServerUrl": "temporal.cloud:7233",
            "flowServerNamespace": "production",
            "flowServerCertBase64": "cert_data",
            "flowServerPrivateKeyBase64": "key_data",
            "flowServerRootCaPem": "ca_pem_data",
            "flowServerDomainOverride": "temporal.cloud",
        }

        config = XiansPlatform._build_temporal_config_from_settings(settings)

        assert config.address == "temporal.cloud:7233"
        assert config.namespace == "production"
        assert config.tls is not None
        assert config.tls.enabled
        assert config.tls.domain == "temporal.cloud"
        assert config.tls.client_cert_pem == "cert_data"
        assert config.tls.client_key_pem == "key_data"
        assert config.tls.root_ca_pem == "ca_pem_data"
        assert config.tls.pem_is_base64

    def test_missing_flowServerUrl_raises_error(self):
        """Test that missing flowServerUrl raises ConfigurationError."""
        from xians.exceptions.v1.errors import ConfigurationError

        settings: dict[str, object] = {}

        with pytest.raises(ConfigurationError, match="flowServerUrl missing"):
            XiansPlatform._build_temporal_config_from_settings(settings)

    def test_empty_flowServerUrl_raises_error(self):
        """Test that empty flowServerUrl raises ConfigurationError."""
        from xians.exceptions.v1.errors import ConfigurationError

        settings = {"flowServerUrl": ""}

        with pytest.raises(ConfigurationError, match="flowServerUrl missing"):
            XiansPlatform._build_temporal_config_from_settings(settings)

