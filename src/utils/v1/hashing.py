"""Hashing utilities for Xians SDK v1."""

import hashlib


def compute_hash(content: str) -> str:
    """
    Compute a SHA-256 hash of the given content.

    This function provides consistent, deterministic hashing for content
    deduplication, cache keys, and idempotency checks.

    Args:
        content: The string content to hash.

    Returns:
        A 64-character hexadecimal string representing the SHA-256 hash.

    Example:
        >>> compute_hash("test content")
        'a1b2c3d4...'  # 64 hex characters
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = ["compute_hash"]
