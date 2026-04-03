"""Logging constants — mirrors C# WorkflowConstants.EnvironmentVariables / ApiEndpoints.

Centralises environment-variable names, API paths, and sensible defaults so
every logging module references a single source of truth.
"""

from __future__ import annotations

__all__ = [
    "CONSOLE_LOG_LEVEL_ENV",
    "SERVER_LOG_LEVEL_ENV",
    "API_LOG_LEVEL_ENV",
    "WORKFLOW_LOG_TO_CONSOLE_ENV",
    "LOGS_API_ENDPOINT",
    "DEFAULT_CONSOLE_LOG_LEVEL",
    "DEFAULT_SERVER_LOG_LEVEL",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_PROCESSING_INTERVAL_SECONDS",
    "MAX_RETRIES",
]

# Environment variable names (mirrors C# WorkflowConstants.EnvironmentVariables)
CONSOLE_LOG_LEVEL_ENV = "CONSOLE_LOG_LEVEL"
SERVER_LOG_LEVEL_ENV = "SERVER_LOG_LEVEL"
API_LOG_LEVEL_ENV = "API_LOG_LEVEL"  # legacy fallback, kept for backward compat
WORKFLOW_LOG_TO_CONSOLE_ENV = "WORKFLOW_LOG_TO_CONSOLE"

# API endpoint (mirrors C# WorkflowConstants.ApiEndpoints.Logs)
LOGS_API_ENDPOINT = "api/agent/logs"

# Default log levels (mirrors C# LoggerFactory defaults)
DEFAULT_CONSOLE_LOG_LEVEL = "DEBUG"
DEFAULT_SERVER_LOG_LEVEL = "ERROR"

# Background processor settings (mirrors C# LoggingServices)
DEFAULT_BATCH_SIZE = 100
DEFAULT_PROCESSING_INTERVAL_SECONDS = 30
MAX_RETRIES = 3
