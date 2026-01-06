"""Standardized exception handling utilities for Xians SDK v1."""

import functools
import logging
from typing import Any, Callable, TypeVar, cast

from ...exceptions.v1.errors import XiansError

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def handle_exceptions(
    *,
    default_return: Any = None,
    raise_on_error: bool = True,
    log_error: bool = True,
    error_message: str | None = None,
) -> Callable[[F], F]:
    """
    Decorator for standardized exception handling with try-catch-finally pattern.

    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            context = {
                "function": func.__name__,
                "module": func.__module__,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()),
            }

            try:
                result = await func(*args, **kwargs)
                return result

            except XiansError as e:
                if log_error:
                    logger.error(
                        f"{error_message or 'SDK error'}: {e.message}",
                        extra={
                            **context,
                            "error_type": type(e).__name__,
                            "error_details": e.details,
                            "cause": str(e.cause) if e.cause else None,
                        },
                        exc_info=True,
                    )

                if raise_on_error:
                    raise
                return default_return

            except Exception as e:
                # Unexpected errors
                if log_error:
                    logger.error(
                        f"{error_message or 'Unexpected error'}: {str(e)}",
                        extra={
                            **context,
                            "error_type": type(e).__name__,
                        },
                        exc_info=True,
                    )

                if raise_on_error:
                    raise
                return default_return

            finally:
                # Cleanup logging
                logger.debug(
                    f"Completed execution of {func.__name__}",
                    extra=context,
                )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            context = {
                "function": func.__name__,
                "module": func.__module__,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()),
            }

            try:
                result = func(*args, **kwargs)
                return result

            except XiansError as e:
                if log_error:
                    logger.error(
                        f"{error_message or 'SDK error'}: {e.message}",
                        extra={
                            **context,
                            "error_type": type(e).__name__,
                            "error_details": e.details,
                            "cause": str(e.cause) if e.cause else None,
                        },
                        exc_info=True,
                    )

                if raise_on_error:
                    raise
                return default_return

            except Exception as e:
                if log_error:
                    logger.error(
                        f"{error_message or 'Unexpected error'}: {str(e)}",
                        extra={
                            **context,
                            "error_type": type(e).__name__,
                        },
                        exc_info=True,
                    )

                if raise_on_error:
                    raise
                return default_return

            finally:
                logger.debug(
                    f"Completed execution of {func.__name__}",
                    extra=context,
                )

        # Return appropriate wrapper based on function type
        if functools.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


class ExceptionContext:
    """
    Context manager for standardized exception handling with try-catch-finally.

    Example:
        >>> async with ExceptionContext("database_operation", cleanup_func=db.close):
        ...     await db.execute(query)
    """

    def __init__(
        self,
        operation_name: str,
        *,
        raise_on_error: bool = True,
        log_error: bool = True,
        cleanup_func: Callable[[], Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Initialize exception context.

        Args:
            operation_name: Name of the operation for logging.
            raise_on_error: Whether to re-raise exceptions.
            log_error: Whether to log errors.
            cleanup_func: Optional cleanup function for finally block.
            error_message: Custom error message prefix.
        """
        self.operation_name = operation_name
        self.raise_on_error = raise_on_error
        self.log_error = log_error
        self.cleanup_func = cleanup_func
        self.error_message = error_message
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self) -> "ExceptionContext":
        """Enter async context."""
        self.logger.debug(f"Starting operation: {self.operation_name}")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit async context with exception handling."""
        try:
            if exc_type is None:
                # Success path
                self.logger.debug(f"Completed operation: {self.operation_name}")
                return False

            # Error path
            if self.log_error:
                if isinstance(exc_val, XiansError):
                    self.logger.error(
                        f"{self.error_message or 'Error in'} {self.operation_name}: {exc_val.message}",
                        extra={
                            "operation": self.operation_name,
                            "error_type": exc_type.__name__,
                            "error_details": exc_val.details,
                        },
                        exc_info=True,
                    )
                else:
                    self.logger.error(
                        f"{self.error_message or 'Error in'} {self.operation_name}: {str(exc_val)}",
                        extra={
                            "operation": self.operation_name,
                            "error_type": exc_type.__name__,
                        },
                        exc_info=True,
                    )

            # Suppress exception if raise_on_error is False
            return not self.raise_on_error

        finally:
            # Cleanup in finally block
            if self.cleanup_func:
                try:
                    if functools.iscoroutinefunction(self.cleanup_func):
                        await self.cleanup_func()
                    else:
                        self.cleanup_func()
                    self.logger.debug(f"Cleanup completed for: {self.operation_name}")
                except Exception as cleanup_error:
                    self.logger.warning(
                        f"Cleanup failed for {self.operation_name}: {str(cleanup_error)}",
                        exc_info=True,
                    )

    def __enter__(self) -> "ExceptionContext":
        """Enter sync context."""
        self.logger.debug(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit sync context with exception handling."""
        try:
            if exc_type is None:
                self.logger.debug(f"Completed operation: {self.operation_name}")
                return False

            if self.log_error:
                if isinstance(exc_val, XiansError):
                    self.logger.error(
                        f"{self.error_message or 'Error in'} {self.operation_name}: {exc_val.message}",
                        extra={
                            "operation": self.operation_name,
                            "error_type": exc_type.__name__,
                            "error_details": exc_val.details,
                        },
                        exc_info=True,
                    )
                else:
                    self.logger.error(
                        f"{self.error_message or 'Error in'} {self.operation_name}: {str(exc_val)}",
                        extra={
                            "operation": self.operation_name,
                            "error_type": exc_type.__name__,
                        },
                        exc_info=True,
                    )

            return not self.raise_on_error

        finally:
            if self.cleanup_func:
                try:
                    self.cleanup_func()
                    self.logger.debug(f"Cleanup completed for: {self.operation_name}")
                except Exception as cleanup_error:
                    self.logger.warning(
                        f"Cleanup failed for {self.operation_name}: {str(cleanup_error)}",
                        exc_info=True,
                    )


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    default: T | None = None,
    log_errors: bool = True,
    **kwargs: Any,
) -> T | None:
    """
    Safely execute a function with exception handling.

    Args:
        func: Function to execute.
        *args: Positional arguments for the function.
        default: Default value to return on error.
        log_errors: Whether to log errors.
        **kwargs: Keyword arguments for the function.

    Returns:
        Function result or default value on error.

    Example:
        >>> result = safe_execute(risky_function, arg1, arg2, default=None)
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(
                f"Error executing {func.__name__}: {str(e)}",
                extra={"function": func.__name__, "error_type": type(e).__name__},
                exc_info=True,
            )
        return default


async def safe_execute_async(
    func: Callable[..., T],
    *args: Any,
    default: T | None = None,
    log_errors: bool = True,
    **kwargs: Any,
) -> T | None:
    """
    Safely execute an async function with exception handling.

    Args:
        func: Async function to execute.
        *args: Positional arguments for the function.
        default: Default value to return on error.
        log_errors: Whether to log errors.
        **kwargs: Keyword arguments for the function.

    Returns:
        Function result or default value on error.

    Example:
        >>> result = await safe_execute_async(async_risky_function, arg1, default=None)
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(
                f"Error executing {func.__name__}: {str(e)}",
                extra={"function": func.__name__, "error_type": type(e).__name__},
                exc_info=True,
            )
        return default


__all__ = [
    "handle_exceptions",
    "ExceptionContext",
    "safe_execute",
    "safe_execute_async",
]

