"""Tests for API key validation in configuration models."""

import pytest
from pydantic import SecretStr, ValidationError

from xians.models.v1.configs import XiansOptions, XiansServerConfig
from xians.constants.v1.core import LLMProvider


class TestAPIKeyValidation:
    """Test API key validation in config models."""

    def test_valid_api_key(self) -> None:
        """Test that valid API keys are accepted."""
        config = XiansServerConfig(
            server_url="https://api.example.com",
            api_key=SecretStr("valid-api-key-12345"),
        )
        assert config.api_key.get_secret_value() == "valid-api-key-12345"

    def test_empty_api_key(self) -> None:
        """Test that empty API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            XiansServerConfig(
                server_url="https://api.example.com",
                api_key=SecretStr(""),
            )
        assert "API key cannot be empty" in str(exc_info.value)

    def test_whitespace_only_api_key(self) -> None:
        """Test that whitespace-only API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            XiansServerConfig(
                server_url="https://api.example.com",
                api_key=SecretStr("   "),
            )
        assert "API key cannot be empty" in str(exc_info.value)

    def test_too_short_api_key(self) -> None:
        """Test that very short API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            XiansServerConfig(
                server_url="https://api.example.com",
                api_key=SecretStr("short"),
            )
        assert "too short" in str(exc_info.value)

    @pytest.mark.parametrize(
        "placeholder",
        [
            "your-api-key",
            "your_api_key",
            "your-api-key-here",
            "xxx-xxx-xxx",
            "placeholder-key-123456",
            "test-key-abc",
            "example-key-12345",
        ],
    )
    def test_placeholder_api_keys(self, placeholder: str) -> None:
        """Test that common placeholder API keys are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            XiansServerConfig(
                server_url="https://api.example.com",
                api_key=SecretStr(placeholder),
            )
        assert "placeholder" in str(exc_info.value).lower()

    def test_api_key_with_leading_trailing_whitespace(self) -> None:
        """Test that API keys with whitespace are trimmed."""
        config = XiansServerConfig(
            server_url="https://api.example.com",
            api_key=SecretStr("  valid-api-key-12345  "),
        )
        # Should be trimmed
        assert config.api_key.get_secret_value() == "valid-api-key-12345"

    def test_xians_options_api_key_validation(self) -> None:
        """Test that API key validation works in XiansOptions."""
        with pytest.raises(ValidationError) as exc_info:
            XiansOptions(
                server_url="https://api.example.com",
                api_key=SecretStr("your-api-key"),
                llm={
                    "provider": LLMProvider.OPENAI,
                    "model": "gpt-4",
                },
            )
        assert "placeholder" in str(exc_info.value).lower()

    def test_xians_options_valid_config(self) -> None:
        """Test that XiansOptions accepts valid configuration."""
        options = XiansOptions(
            server_url="https://api.example.com",
            api_key=SecretStr("sk-valid-api-key-123456"),
            llm={
                "provider": LLMProvider.OPENAI,
                "model": "gpt-4",
                "api_key": SecretStr("sk-openai-key-123456"),
            },
        )
        assert options.api_key.get_secret_value() == "sk-valid-api-key-123456"

    def test_case_insensitive_placeholder_detection(self) -> None:
        """Test that placeholder detection is case-insensitive."""
        with pytest.raises(ValidationError) as exc_info:
            XiansServerConfig(
                server_url="https://api.example.com",
                api_key=SecretStr("YOUR-API-KEY-HERE"),
            )
        assert "placeholder" in str(exc_info.value).lower()

    def test_valid_api_key_containing_valid_words(self) -> None:
        """Test that API keys containing 'api' or 'key' are accepted."""
        # Should NOT be rejected just because it contains common words
        # Only reject if it matches placeholder patterns
        config = XiansServerConfig(
            server_url="https://api.example.com",
            api_key=SecretStr("sk-proj-abcdef123456789"),
        )
        assert config.api_key.get_secret_value() == "sk-proj-abcdef123456789"

