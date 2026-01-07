"""Safe access utilities for nested dictionaries in Xians SDK v1."""

from typing import Any


def safe_dict_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely retrieve a nested value from a dictionary.
    """
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


__all__ = ["safe_dict_get"]

