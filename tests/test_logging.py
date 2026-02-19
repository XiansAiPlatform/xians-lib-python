"""Tests for logging configuration."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.configs.v1.logging import (
    STRUCTLOG_AVAILABLE,
    LoggerMixin,
    configure_logging,
    get_logger,
    log_context,
)


class TestLoggingConfiguration:
    """Test suite for logging configuration."""

    def test_configure_logging_default(self) -> None:
        """Test default logging configuration."""
        configure_logging()

        logger = get_logger(__name__)
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_configure_logging_with_level(self) -> None:
        """Test logging configuration with custom level."""
        configure_logging(log_level="DEBUG")

        logger = get_logger(__name__)
        # Root logger should be at DEBUG level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_logging_with_file(self) -> None:
        """Test logging configuration with file output."""
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            configure_logging(log_level="INFO", log_file=log_file)

            logger = get_logger(__name__)
            logger.info("Test message")

            # Check file was created and has content
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

    def test_configure_logging_invalid_level(self) -> None:
        """Test that invalid log level raises error."""
        with pytest.raises(ValueError, match="Invalid log level"):
            configure_logging(log_level="INVALID")

    def test_get_logger(self) -> None:
        """Test getting a logger instance."""
        logger = get_logger("test.module")

        assert logger is not None
        assert logger.name == "test.module"

    def test_log_context(self) -> None:
        """Test creating log context."""
        context = log_context(user_id="123", action="login", status="success")

        assert context == {
            "user_id": "123",
            "action": "login",
            "status": "success",
        }

    def test_logger_mixin(self) -> None:
        """Test LoggerMixin provides logger property."""
        class TestClass(LoggerMixin):
            def do_something(self):
                self.logger.info("Doing something")
                return "done"

        obj = TestClass()
        assert hasattr(obj, "logger")
        assert isinstance(obj.logger, logging.Logger)

        result = obj.do_something()
        assert result == "done"

    def test_structured_logging_availability(self) -> None:
        """Test that STRUCTLOG_AVAILABLE flag is set correctly."""
        assert isinstance(STRUCTLOG_AVAILABLE, bool)
        # It's either True or False depending on whether structlog is installed

    @pytest.mark.skipif(not STRUCTLOG_AVAILABLE, reason="structlog not installed")
    def test_configure_structured_logging(self) -> None:
        """Test structured logging configuration (if available)."""
        configure_logging(
            log_level="INFO",
            enable_structured=True,
        )

        logger = get_logger(__name__)
        logger.info("Structured log message", extra=log_context(key="value"))

        # If we get here without errors, structured logging is working
        assert True

