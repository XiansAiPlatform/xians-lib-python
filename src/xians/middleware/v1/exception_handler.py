"""Global exception handler middleware for Xians SDK v1."""

import functools
import logging
from typing import Any, Callable, TypeVar, cast

from ...exceptions.v1.errors import XiansError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ExceptionHandlerMiddleware:
    """
    Global exception handler middleware for consistent error handling across the SDK.
    """

    def __init__(self) -> None:
        """Initialize the exception handler middleware."""
        self._handlers: dict[type[Exception], Callable[[Exception], Any]] = {}
        self._error_count = 0
        self._error_log: list[dict[str, Any]] = []

    def register_handler(
        self,
        exception_type: type[Exception],
        handler: Callable[[Exception], Any],
    ) -> None:
        self._handlers[exception_type] = handler
        logger.debug(f"Registered handler for {exception_type.__name__}")

    def handle_exception(
        self,
        exc: Exception,
        context: dict[str, Any] | None = None,
        re_raise: bool = False,
    ) -> Any:
        context = context or {}

        self._error_count += 1
        self._log_exception(exc, context)
        handler = self._handlers.get(type(exc))
        if handler:
            try:
                result = handler(exc)
                logger.debug(f"Custom handler executed for {type(exc).__name__}")
                return result
            except Exception as handler_error:
                logger.error(
                    f"Custom handler failed for {type(exc).__name__}: {handler_error}",
                    exc_info=True,
                )

        if isinstance(exc, XiansError):
            return self._handle_xians_error(exc, context)

        return self._handle_standard_error(exc, context, re_raise)

    def _log_exception(self, exc: Exception, context: dict[str, Any]) -> None:
        error_entry = {
            "error_count": self._error_count,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "context": context,
        }

        self._error_log.append(error_entry)

        log_level = logging.ERROR
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            log_level = logging.WARNING

        logger.log(
            log_level,
            f"Exception handled: {type(exc).__name__}: {str(exc)}",
            extra={
                "error_type": type(exc).__name__,
                "context": context,
            },
            exc_info=True,
        )

    def _handle_xians_error(
        self,
        exc: XiansError,
        context: dict[str, Any],
    ) -> None:
        logger.error(
            f"Xians SDK Error: {exc.message}",
            extra={
                "error_type": type(exc).__name__,
                "error_details": exc.details,
                "cause": str(exc.cause) if exc.cause else None,
                "context": context,
            },
            exc_info=True,
        )
        return None

    def _handle_standard_error(
        self,
        exc: Exception,
        context: dict[str, Any],
        re_raise: bool = False,
    ) -> None:
        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={
                "error_type": type(exc).__name__,
                "context": context,
            },
            exc_info=True,
        )

        if re_raise:
            raise exc

        return None

    def get_error_count(self) -> int:
        return self._error_count

    def get_error_log(self) -> list[dict[str, Any]]:
        return self._error_log.copy()

    def clear_error_log(self) -> None:
        self._error_log.clear()
        logger.debug("Error log cleared")


_global_middleware: ExceptionHandlerMiddleware | None = None


def initialize_middleware() -> ExceptionHandlerMiddleware:
    global _global_middleware
    if _global_middleware is None:
        _global_middleware = ExceptionHandlerMiddleware()
        logger.debug("Global exception handler middleware initialized")
    return _global_middleware


def get_middleware() -> ExceptionHandlerMiddleware:
    global _global_middleware
    if _global_middleware is None:
        raise RuntimeError(
            "Exception handler middleware not initialized. "
            "Call initialize_middleware() first."
        )
    return _global_middleware


def with_exception_handling(
    *,
    context: dict[str, Any] | None = None,
    re_raise: bool = False,
    operation_name: str | None = None,
) -> Callable[[F], F]:

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            op_name = operation_name or func.__name__
            op_context = {
                "operation": op_name,
                "module": func.__module__,
                **(context or {}),
            }

            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                middleware = get_middleware()
                middleware.handle_exception(exc, op_context, re_raise=re_raise)
                return None

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            op_name = operation_name or func.__name__
            op_context = {
                "operation": op_name,
                "module": func.__module__,
                **(context or {}),
            }

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                middleware = get_middleware()
                middleware.handle_exception(exc, op_context, re_raise=re_raise)
                return None

        if functools.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


class ExceptionHandlingContext:

    def __init__(
        self,
        operation_name: str,
        context: dict[str, Any] | None = None,
        re_raise: bool = False,
        cleanup_func: Callable[[], Any] | None = None,
    ) -> None:
        self.operation_name = operation_name
        self.context = {
            "operation": operation_name,
            **(context or {}),
        }
        self.re_raise = re_raise
        self.cleanup_func = cleanup_func
        self.middleware = get_middleware()

    async def __aenter__(self) -> "ExceptionHandlingContext":
        logger.debug(f"Starting operation: {self.operation_name}")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        try:
            if exc_type is None:
                logger.debug(f"Completed operation: {self.operation_name}")
                return False

            if exc_val:
                self.middleware.handle_exception(
                    exc_val,
                    self.context,
                    re_raise=self.re_raise,
                )
                return not self.re_raise

            return False

        finally:
            if self.cleanup_func:
                try:
                    if functools.iscoroutinefunction(self.cleanup_func):
                        await self.cleanup_func()
                    else:
                        self.cleanup_func()
                    logger.debug(f"Cleanup completed for: {self.operation_name}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Cleanup failed for {self.operation_name}: {cleanup_error}",
                        exc_info=True,
                    )

    def __enter__(self) -> "ExceptionHandlingContext":
        logger.debug(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:

        try:
            if exc_type is None:
                logger.debug(f"Completed operation: {self.operation_name}")
                return False

            if exc_val:
                self.middleware.handle_exception(
                    exc_val,
                    self.context,
                    re_raise=self.re_raise,
                )
                return not self.re_raise

            return False

        finally:
            if self.cleanup_func:
                try:
                    self.cleanup_func()
                    logger.debug(f"Cleanup completed for: {self.operation_name}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Cleanup failed for {self.operation_name}: {cleanup_error}",
                        exc_info=True,
                    )


__all__ = [
    "ExceptionHandlerMiddleware",
    "initialize_middleware",
    "get_middleware",
    "with_exception_handling",
    "ExceptionHandlingContext",
]

