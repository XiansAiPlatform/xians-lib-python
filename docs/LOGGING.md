# Logging in Xians Python SDK

## Overview

The Xians Python SDK provides a context-aware logging system that automatically captures workflow metadata (workflow ID, agent name, tenant ID, participant ID) and routes logs to the console **and/or** the Xians server. It wraps Python's standard `logging` module so you can use familiar patterns while gaining automatic context enrichment and server upload.

---

## Quick Start

```python
from xians.logging import XiansLogger

# Create a logger for your class
logger = XiansLogger.for_type(MyActivity)

# Use standard logging methods
logger.debug("Processing started")
logger.info("Fetched %d items", count)
logger.warning("Skipping item with no link: %s", title)
logger.error("Workflow failed: %s", str(exc), exc_info=True)
```

---

## Logging in Workflows and Activities

| Context        | Logger                  | How to Obtain                                  |
|----------------|-------------------------|-------------------------------------------------|
| **Activities** | `logging.Logger`        | `XiansLogger.for_type(MyClass)` or `XiansLogger.get_logger(MyClass)` |
| **Workflows**  | `logging.getLogger()`   | Standard `logging.getLogger(__name__)`           |
| **Anywhere**   | `logging.Logger`        | `XiansLogger.for_type("my.logger.name")`        |

### Activity Logging

```python
from temporalio import activity
from xians.logging import XiansLogger


class NewsSearchActivities:
    _logger = XiansLogger.for_type("NewsSearchActivities")

    @activity.defn
    async def fetch_news_sources(self) -> list[dict]:
        sources = await self._data.get_active_sources()
        self._logger.debug("Fetched %d generic news sources", len(sources))
        return sources

    @activity.defn
    async def validate_and_save(self, item: dict) -> int:
        if not item.get("link"):
            self._logger.warning("Skipping item with no link: %s", item.get("title"))
            return 0
        self._logger.debug("Saved article for %s", item["link"])
        return 1
```

### Workflow Logging

```python
import logging
from temporalio import workflow

logger = logging.getLogger(__name__)

@workflow.defn(name="MyAgent:News Search Workflow")
class NewsSearchWorkflow:
    @workflow.run
    async def run(self) -> str:
        logger.info("Starting news search workflow")
        # ... workflow logic ...
        return "done"
```

### Automatic Context Capture

Both workflow and activity logs **automatically** include workflow metadata when uploaded to the server:

```json
{
  "workflowId": "tenant-abc:Market Analysts:News Search Workflow:user-123",
  "workflowRunId": "def456-789-abc",
  "workflowType": "Market Analysts:News Search Workflow",
  "agent": "Market Analysts",
  "participantId": "user-123",
  "tenantId": "tenant-abc",
  "level": "Information",
  "message": "Fetched 4 generic news sources",
  "createdAt": "2026-01-25T10:30:00Z"
}
```

**You don't need to add this context manually.** The `ApiLogHandler` extracts it from `XiansContext` automatically.

---

## Server Upload Configuration

Server upload is **disabled by default**. To enable it, set `server_log_level` during platform initialization.

### Console vs Server Log Levels

Two independent thresholds control where logs go:

| Configuration        | Where Logs Go       | Default     |
|----------------------|---------------------|-------------|
| **console_log_level**| Terminal / console  | `INFO`      |
| **server_log_level** | Xians server        | *Disabled*  |

With `console_log_level="DEBUG"` and `server_log_level="INFO"`:

- **Console** shows: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Server** receives: INFO, WARNING, ERROR, CRITICAL

```
Your Code                Console              Server
   ├─ debug()         ────┼──> Displayed       │     (Console only)
   ├─ info()          ────┼──> Displayed   ────┼──> Uploaded
   ├─ warning()       ────┼──> Displayed   ────┼──> Uploaded
   ├─ error()         ────┼──> Displayed   ────┼──> Uploaded
   └─ critical()      ────┼──> Displayed   ────┼──> Uploaded
```

### Enable Server Upload

Set `server_log_level` in code or via environment variables:

```python
from xians.platform.v1 import XiansPlatform, XiansOptions

platform = await XiansPlatform.initialize(XiansOptions(
    server_url="https://your-server.xians.ai",
    api_key="<your-pfx-certificate>",
    server_log_level="INFO",       # Enables upload; INFO and above sent
    console_log_level="DEBUG",     # Console shows DEBUG and above
))
```

Or via environment variables:

```bash
CONSOLE_LOG_LEVEL=DEBUG
SERVER_LOG_LEVEL=INFO
```

**Priority:** Code configuration > Environment variables > Defaults

### Log Levels Reference

| Level       | Python Constant    | Server Name     | Example                            |
|-------------|--------------------|-----------------|------------------------------------|
| `DEBUG`     | `logging.DEBUG`    | `Debug`         | "Fetched 4 generic news sources"   |
| `INFO`      | `logging.INFO`     | `Information`   | "News search completed"            |
| `WARNING`   | `logging.WARNING`  | `Warning`       | "Skipping item with no link"       |
| `ERROR`     | `logging.ERROR`    | `Error`         | "Workflow failed: connection timeout" |
| `CRITICAL`  | `logging.CRITICAL` | `Critical`      | "Database connection lost"          |

---

## How Logs Are Uploaded to the Server

### Batch Upload Mechanism

Logs are **not** uploaded immediately. They are queued in memory and uploaded in periodic batches:

| Setting               | Default     | Description                              |
|-----------------------|-------------|------------------------------------------|
| **Batch Size**        | 100 logs    | Maximum logs per upload batch            |
| **Upload Interval**   | 30 seconds  | Time between batch uploads               |
| **Queue Type**        | In-memory   | Thread-safe deque                        |
| **Retry**             | 3 attempts  | Failed uploads are requeued              |
| **Shutdown**          | Flush all   | Remaining logs uploaded on exit          |

### What This Means for You

**Delay:** Logs may take **up to 30 seconds** to appear on the server dashboard.

**Reliability:**
- Failed uploads are automatically retried (up to 3 times)
- Logs are flushed on application shutdown
- Network issues won't cause immediate log loss

**Performance:**
- Minimal impact on application performance
- Batching reduces server API calls
- Background thread doesn't block your code

### Configuration (Advanced)

```python
from xians.logging import LoggingServices

# Customize batch upload settings
svc = LoggingServices.get_instance()
svc.configure_batch_settings(
    batch_size=50,              # Smaller batches
    processing_interval_s=15,   # Upload every 15 seconds
)

# Enable verbose diagnostics for debugging the logging system itself
svc.enable_verbose_diagnostics(True)

# Check logging statistics
queued, retrying = svc.get_stats()
print(f"Queued logs: {queued}, Retrying: {retrying}")
```

**When to customize:**
- **Smaller batches + frequent uploads** → Critical systems needing near real-time logs
- **Larger batches + less frequent** → High-volume systems to reduce API calls

---

## Architecture

### Module Structure

```
xians/logging/
├── __init__.py              # Public API exports
├── models/
│   ├── __init__.py
│   └── log.py               # Log Pydantic model (server contract)
├── api_handler.py           # Python logging.Handler → server queue
├── logging_services.py      # Background batch processor & uploader
└── xians_logger.py          # Context-aware logger factory
```

### Component Roles (C# Mapping)

| Python Component       | C# Equivalent               | Role                                          |
|------------------------|------------------------------|-----------------------------------------------|
| `Log`                  | `Xians.Lib.Logging.Models.Log` | Pydantic model representing a log entry      |
| `ApiLogHandler`        | `ApiLogger` / `ApiLoggerProvider` | `logging.Handler` that creates `Log` entries and enqueues them |
| `LoggingServices`      | `LoggingServices`            | Singleton background processor: queue + batch upload |
| `XiansLogger`          | `XiansLogger` / `Logger<T>` | Factory for obtaining context-aware loggers    |

### Data Flow

```
Your Code
   │
   ├─ logger.info("message")
   │      │
   │      ▼
   │  Python logging framework
   │      │
   │      ├─── StreamHandler ──────► Console output
   │      │
   │      └─── ApiLogHandler
   │               │
   │               ├── Checks server_log_level threshold
   │               ├── Extracts context from XiansContext
   │               ├── Creates Log model with metadata
   │               └── Enqueues to LoggingServices
   │                        │
   │                        ▼
   │               Background Thread (every 30s)
   │                        │
   │                        ├── Dequeues batch (up to 100)
   │                        ├── POST /api/agent/logs
   │                        │
   │                        ├── Success → clear retry counts
   │                        └── Failure → requeue (max 3 retries)
```

### Context Extraction

The `ApiLogHandler` automatically extracts the following from `XiansContext`:

| Field            | Source                                    |
|------------------|-------------------------------------------|
| `workflowId`     | `XiansContext.safe_workflow_id()`          |
| `workflowType`   | `XiansContext.safe_workflow_type()`        |
| `agent`          | `XiansContext.safe_agent_name()`           |
| `tenantId`       | `XiansContext.safe_tenant_id()`            |
| `participantId`  | `XiansContext.safe_participant_id()`       |
| `activation`     | `XiansContext.safe_id_postfix()`           |

These are populated from Python `contextvars` and Temporal's activity/workflow info when available.

### Thread Safety

- The log queue uses a `threading.Lock` for safe access from any thread
- The background processor runs on a dedicated daemon thread
- `LoggingServices` is a singleton with thread-safe initialization
- `XiansContext` uses `contextvars` for async-safe per-task context

---

## Troubleshooting

### "My logs aren't appearing on the server"

**Most common cause:** Server logging is disabled by default.

**Solution:** Set `server_log_level` during initialization:

```python
platform = await XiansPlatform.initialize(XiansOptions(
    server_url=server_url,
    api_key=api_key,
    server_log_level="WARNING",  # This enables server logging
))
```

### Verification

```python
from xians.logging import LoggingServices, XiansLogger

# Log a test message at server threshold level
logger = XiansLogger.for_type("test")
logger.warning("Test message — server logging verification")

# Check logging service status
svc = LoggingServices.get_instance()
queued, retrying = svc.get_stats()
print(f"Queued logs: {queued}, Retrying: {retrying}")
```

If `queued > 0`, server logging is working and logs are queued for upload.

### "Logs are queued but never uploaded"

Check that:
1. The platform's HTTP client can reach the server
2. The API key (certificate) is valid
3. Enable verbose diagnostics: `LoggingServices.get_instance().enable_verbose_diagnostics(True)`

---

## API Reference

### `XiansLogger`

```python
from xians.logging import XiansLogger

# By class
logger = XiansLogger.for_type(MyActivity)

# By string name
logger = XiansLogger.for_type("my.module.name")

# Aliases
logger = XiansLogger.get_logger(MyActivity)      # Same as for_type
logger = XiansLogger.for_ilogger(MyActivity)      # C# ForILogger parity
```

### `LoggingServices`

```python
from xians.logging import LoggingServices

svc = LoggingServices.get_instance()
svc.configure_batch_settings(batch_size=50, processing_interval_s=15)
svc.enable_verbose_diagnostics(True)
queued, retrying = svc.get_stats()
svc.shutdown()
```

### `XiansOptions` logging fields

```python
XiansOptions(
    server_url="...",
    api_key="...",
    console_log_level="DEBUG",      # Controls console output
    server_log_level="INFO",        # Controls server upload (None = disabled)
)
```

### Environment Variables

| Variable            | Purpose                                         | Default  |
|---------------------|-------------------------------------------------|----------|
| `CONSOLE_LOG_LEVEL` | Minimum level for console output                | `INFO`   |
| `SERVER_LOG_LEVEL`  | Minimum level for server upload (unset=disabled)| Disabled |
| `API_LOG_LEVEL`     | Legacy alias for `SERVER_LOG_LEVEL`             | —        |
