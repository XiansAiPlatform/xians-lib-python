"""Retry utilities for Xians SDK v1."""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from ...constants.v1.core import DEFAULT_RETRY_ATTEMPTS

logger = logging.getLogger(__name__)

T = TypeVar("T")


def create_retry_decorator(
    max_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Create a decorator for retrying functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3).
        exceptions: Tuple of exception types to catch and retry.
        backoff_factor: Multiplier for delay between retries (default: 2.0).
        initial_delay: Initial delay in seconds before first retry (default: 1.0).

    Returns:
        A decorator function that adds retry logic.

    Example:
        >>> @create_retry_decorator(max_attempts=3)
        >>> async def fetch_data():
        ...     # API call that may fail
        ...     return await client.get("/data")
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")

            # If we get here, all attempts failed
            if last_exception:
                raise last_exception

            # This shouldn't happen, but satisfy type checker
            raise RuntimeError(f"Retry failed for {func.__name__}")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        import time

                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")

            # If we get here, all attempts failed
            if last_exception:
                raise last_exception

            # This shouldn't happen, but satisfy type checker
            raise RuntimeError(f"Retry failed for {func.__name__}")

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


__all__ = ["create_retry_decorator"]
