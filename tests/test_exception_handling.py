"""Tests for exception handling utilities."""

import pytest

from src.exceptions.v1.errors import ConfigurationError, XiansError
from src.utils.v1.exception_handling import (
    ExceptionContext,
    handle_exceptions,
    safe_execute,
    safe_execute_async,
)


class TestHandleExceptionsDecorator:
    """Test suite for handle_exceptions decorator."""

    def test_decorator_successful_sync_function(self) -> None:
        """Test decorator with successful sync function."""
        @handle_exceptions()
        def successful_func(x: int, y: int) -> int:
            return x + y

        result = successful_func(2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_decorator_successful_async_function(self) -> None:
        """Test decorator with successful async function."""
        @handle_exceptions()
        async def successful_async_func(x: int, y: int) -> int:
            return x + y

        result = await successful_async_func(2, 3)
        assert result == 5

    def test_decorator_raises_on_error(self) -> None:
        """Test decorator raises exception when raise_on_error=True."""
        @handle_exceptions(raise_on_error=True)
        def failing_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_func()

    def test_decorator_returns_default_on_error(self) -> None:
        """Test decorator returns default value when raise_on_error=False."""
        @handle_exceptions(raise_on_error=False, default_return="default")
        def failing_func() -> str:
            raise ValueError("Test error")

        result = failing_func()
        assert result == "default"

    @pytest.mark.asyncio
    async def test_decorator_async_raises_on_error(self) -> None:
        """Test decorator raises exception for async function."""
        @handle_exceptions(raise_on_error=True)
        async def failing_async_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_async_func()

    @pytest.mark.asyncio
    async def test_decorator_async_returns_default(self) -> None:
        """Test decorator returns default for async function on error."""
        @handle_exceptions(raise_on_error=False, default_return=None)
        async def failing_async_func() -> str:
            raise ValueError("Test error")

        result = await failing_async_func()
        assert result is None

    def test_decorator_handles_xians_error(self) -> None:
        """Test decorator handles XiansError specifically."""
        @handle_exceptions(raise_on_error=False, default_return="handled")
        def func_with_xians_error() -> str:
            raise ConfigurationError(
                "Config error",
                details={"key": "value"},
            )

        result = func_with_xians_error()
        assert result == "handled"


class TestExceptionContext:
    """Test suite for ExceptionContext manager."""

    @pytest.mark.asyncio
    async def test_async_context_success(self) -> None:
        """Test async context manager with successful operation."""
        async with ExceptionContext("test_operation"):
            result = 1 + 1

        assert result == 2

    @pytest.mark.asyncio
    async def test_async_context_with_exception_raises(self) -> None:
        """Test async context manager raises exception by default."""
        with pytest.raises(ValueError, match="Test error"):
            async with ExceptionContext("test_operation"):
                raise ValueError("Test error")

    @pytest.mark.asyncio
    async def test_async_context_suppresses_exception(self) -> None:
        """Test async context manager can suppress exceptions."""
        result = None
        async with ExceptionContext("test_operation", raise_on_error=False):
            raise ValueError("Test error")
            result = "should not reach here"

        # Exception was suppressed, execution continued
        assert result is None

    @pytest.mark.asyncio
    async def test_async_context_with_cleanup(self) -> None:
        """Test async context manager calls cleanup function."""
        cleanup_called = []

        def cleanup():
            cleanup_called.append(True)

        async with ExceptionContext("test_operation", cleanup_func=cleanup):
            pass

        assert len(cleanup_called) == 1

    @pytest.mark.asyncio
    async def test_async_context_cleanup_on_error(self) -> None:
        """Test async context manager calls cleanup even on error."""
        cleanup_called = []

        def cleanup():
            cleanup_called.append(True)

        try:
            async with ExceptionContext(
                "test_operation",
                cleanup_func=cleanup,
                raise_on_error=True,
            ):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Cleanup should still be called
        assert len(cleanup_called) == 1

    def test_sync_context_success(self) -> None:
        """Test sync context manager with successful operation."""
        with ExceptionContext("test_operation"):
            result = 1 + 1

        assert result == 2

    def test_sync_context_with_exception(self) -> None:
        """Test sync context manager handles exceptions."""
        with pytest.raises(ValueError):
            with ExceptionContext("test_operation"):
                raise ValueError("Test error")

    def test_sync_context_with_cleanup(self) -> None:
        """Test sync context manager calls cleanup function."""
        cleanup_called = []

        def cleanup():
            cleanup_called.append(True)

        with ExceptionContext("test_operation", cleanup_func=cleanup):
            pass

        assert len(cleanup_called) == 1


class TestSafeExecute:
    """Test suite for safe_execute functions."""

    def test_safe_execute_success(self) -> None:
        """Test safe_execute with successful function."""
        def add(a: int, b: int) -> int:
            return a + b

        result = safe_execute(add, 2, 3)
        assert result == 5

    def test_safe_execute_with_error(self) -> None:
        """Test safe_execute returns default on error."""
        def failing_func() -> int:
            raise ValueError("Error")

        result = safe_execute(failing_func, default=0)
        assert result == 0

    def test_safe_execute_with_kwargs(self) -> None:
        """Test safe_execute with keyword arguments."""
        def func_with_kwargs(a: int, b: int = 10) -> int:
            return a + b

        result = safe_execute(func_with_kwargs, 5, b=20)
        assert result == 25

    @pytest.mark.asyncio
    async def test_safe_execute_async_success(self) -> None:
        """Test safe_execute_async with successful function."""
        async def add_async(a: int, b: int) -> int:
            return a + b

        result = await safe_execute_async(add_async, 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_safe_execute_async_with_error(self) -> None:
        """Test safe_execute_async returns default on error."""
        async def failing_async_func() -> int:
            raise ValueError("Error")

        result = await safe_execute_async(failing_async_func, default=0)
        assert result == 0

    @pytest.mark.asyncio
    async def test_safe_execute_async_with_kwargs(self) -> None:
        """Test safe_execute_async with keyword arguments."""
        async def async_func_with_kwargs(a: int, b: int = 10) -> int:
            return a + b

        result = await safe_execute_async(async_func_with_kwargs, 5, b=20)
        assert result == 25

