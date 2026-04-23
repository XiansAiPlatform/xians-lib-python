"""Xians Python SDK.

Temporal-native agent runtime with Xians platform integration.

This package provides:
- Temporal workflow runtime for durable AI agents
- Xians server integration (knowledge, documents, conversations)
- LLM framework-agnostic abstractions
- Enterprise-grade configuration and error handling

The single source of truth for the package version is ``pyproject.toml``.
``__version__`` is resolved dynamically from the installed distribution
metadata so it stays in sync automatically.
"""

from importlib.metadata import PackageNotFoundError, version as _dist_version

__author__ = "Xians Platform"
__license__ = "MIT"

try:
    __version__ = _dist_version("xians-lib-python")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__author__", "__license__", "__version__"]
