"""Utilities for loading TLS materials (PEM or file paths) for Temporal connections.

All functions are strict, typed, and raise clear exceptions on failure.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TLSMaterialError(ValueError):
    """Raised when TLS materials cannot be loaded or are invalid."""


def load_bytes_from_path(path: str) -> bytes:
    """Load bytes from a filesystem path.

    Args:
        path: String path to a file.

    Returns:
        Raw bytes of the file contents.

    Raises:
        TLSMaterialError: If the file is missing or unreadable.
    """
    p = Path(path)
    try:
        data = p.read_bytes()
        if not data:
            raise TLSMaterialError(f"File at '{path}' is empty; expected PEM bytes.")
        return data
    except FileNotFoundError as e:
        raise TLSMaterialError(
            f"TLS file not found at '{path}'. Ensure the path exists and is readable."
        ) from e
    except PermissionError as e:
        raise TLSMaterialError(
            f"Permission denied reading TLS file at '{path}'. Check file permissions."
        ) from e
    except Exception as e:
        raise TLSMaterialError(
            f"Failed to read TLS file at '{path}': {e}"
        ) from e


def pem_to_bytes(pem: str, pem_is_base64: bool) -> bytes:
    """Convert PEM string to raw bytes, optionally base64-decoding.

    Args:
        pem: PEM content string, possibly base64-encoded.
        pem_is_base64: If True, base64-decode before returning.

    Returns:
        Raw bytes of the PEM.
    """
    if pem_is_base64:
        try:
            return base64.b64decode(pem)
        except Exception as e:
            raise TLSMaterialError(
                "Provided PEM appears invalid base64; ensure the value is base64-encoded."
            ) from e
    return pem.encode("utf-8")


def resolve_cert_bytes(pem: Optional[str], path: Optional[str], pem_is_base64: bool) -> Optional[bytes]:
    """Resolve certificate/key bytes from either PEM string or file path.

    Preference: if PEM is provided, use it; otherwise, use file path; else None.

    Args:
        pem: Optional PEM string.
        path: Optional file path.
        pem_is_base64: Whether to base64-decode provided PEM.

    Returns:
        Optional bytes.
    """
    if pem:
        return pem_to_bytes(pem, pem_is_base64)
    if path:
        return load_bytes_from_path(path)
    return None

