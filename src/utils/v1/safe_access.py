"""Safe data access utilities for Xians SDK v1."""

from typing import Any


def safe_dict_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely retrieve a value from a nested dictionary.

    Traverses the dictionary using the provided keys, returning the default
    value if any key is missing or if an intermediate value is not a dictionary.

    Args:
        data: The dictionary to search.
        *keys: Variable number of keys to traverse the nested structure.
        default: Default value to return if key path is not found (default: None).

    Returns:
        The value at the specified key path, or the default value if not found.

    Example:
        >>> data = {"level1": {"level2": {"level3": "value"}}}
        >>> safe_dict_get(data, "level1", "level2", "level3")
        'value'
        >>> safe_dict_get(data, "level1", "missing", default="not found")
        'not found'
    """
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        if key not in current:
            return default

        current = current[key]

    return current


__all__ = ["safe_dict_get"]
