"""
Unit tests for utility functions.
"""

import logging

import pytest

from xians.utils.v1 import compute_hash, safe_dict_get, setup_logging


@pytest.mark.unit
def test_compute_hash() -> None:
    """Test compute_hash produces consistent hashes."""
    content = "test content"
    hash1 = compute_hash(content)
    hash2 = compute_hash(content)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 produces 64 hex characters
    assert isinstance(hash1, str)


@pytest.mark.unit
def test_compute_hash_different_content() -> None:
    """Test compute_hash produces different hashes for different content."""
    hash1 = compute_hash("content1")
    hash2 = compute_hash("content2")

    assert hash1 != hash2


@pytest.mark.unit
def test_setup_logging_default() -> None:
    """Test setup_logging with default settings."""
    logger = setup_logging()

    assert isinstance(logger, logging.Logger)
    assert logger.name == "xians"
    assert logger.level == logging.INFO


@pytest.mark.unit
def test_setup_logging_debug() -> None:
    """Test setup_logging with DEBUG level."""
    logger = setup_logging(level="DEBUG")

    assert logger.level == logging.DEBUG


@pytest.mark.unit
def test_safe_dict_get_simple() -> None:
    """Test safe_dict_get with simple path."""
    data = {"key": "value"}

    assert safe_dict_get(data, "key") == "value"
    assert safe_dict_get(data, "missing") is None
    assert safe_dict_get(data, "missing", default="default") == "default"


@pytest.mark.unit
def test_safe_dict_get_nested() -> None:
    """Test safe_dict_get with nested paths."""
    data = {"level1": {"level2": {"level3": "deep value"}}}

    assert safe_dict_get(data, "level1", "level2", "level3") == "deep value"
    assert safe_dict_get(data, "level1", "level2") == {"level3": "deep value"}


@pytest.mark.unit
def test_safe_dict_get_missing_nested() -> None:
    """Test safe_dict_get with missing nested keys."""
    data = {"level1": {"level2": "value"}}

    assert safe_dict_get(data, "level1", "missing", "key") is None
    assert safe_dict_get(data, "level1", "missing", "key", default=42) == 42


@pytest.mark.unit
def test_safe_dict_get_non_dict() -> None:
    """Test safe_dict_get when intermediate value is not a dict."""
    data = {"key": "string_value"}

    # Trying to access nested key in a string returns default
    assert safe_dict_get(data, "key", "nested") is None
    assert safe_dict_get(data, "key", "nested", default="default") == "default"
