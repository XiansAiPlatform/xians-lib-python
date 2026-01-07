import pytest
from pydantic import SecretStr

from xians.constants.v1.core import LLMProvider
from xians.models.v1.configs import LLMConfig, TemporalConfig, XiansOptions


@pytest.fixture
def sample_temporal_config() -> TemporalConfig:
    """Provide a sample Temporal configuration for testing."""
    return TemporalConfig(
        host="localhost",
        port=7233,
        namespace="test-namespace",
        task_queue="test-queue",
    )


@pytest.fixture
def sample_llm_config() -> LLMConfig:
    """Provide a sample LLM configuration for testing."""
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
        api_key=SecretStr("test-api-key"),
        temperature=0.7,
        max_tokens=2048,
    )


@pytest.fixture
def sample_xians_options() -> XiansOptions:
    """Provide sample XiansOptions for testing (without LLM - no longer required)."""
    return XiansOptions(
        server_url="https://api.test.xians.ai",
        api_key=SecretStr("test-xians-api-key"),
        log_level="DEBUG",
    )
