# Workflow Logs — Python SDK

Mirrors the C# `Xians.Lib.Logging` namespace. All log records are uploaded to
`POST /api/agent/logs` for the Manager UI Workflow Log Explorer.

## Architecture

```
src/xians/agents/workflow_logs/
├── constants.py            # Env-var names, defaults, API path
├── logger_factory.py       # Centralized level parsing & config    ← C# LoggerFactory
├── logging_services.py     # Global queue + background thread      ← C# LoggingServices
├── api_logger_handler.py   # Python logging.Handler → server       ← C# ApiLoggerProvider / ApiLogger
├── xians_logger.py         # User-facing Logger (primary API)      ← C# Logger<T> / XiansLogger
├── log_emitter.py          # Per-activity emitter (backward compat)
├── log_service.py          # HTTP transport (level format negotiation)
├── trace_utils.py          # OpenTelemetry trace/span IDs (shared by handler + emitter)
└── models.py               # WorkflowLogRequest model              ← C# Log
```

**Public package exports** (`from xians.agents.workflow_logs import …`): `XiansLogger`, `LoggingServices`, `ApiLoggerHandler`, `WorkflowLogEmitter`, `WorkflowLogService`, `WorkflowLogLevelName`, `WorkflowLogRequest`. Lower-level helpers (e.g. `parse_log_level`, `setup_root_logging`) live in `xians.agents.workflow_logs.logger_factory` and are not re-exported from the package root.

## Quick Start

Server logging is **automatic** when `server_log_level` is set in `XiansOptions`.
Use `XiansLogger` (the SDK's own logger) in your agent code — it stamps every log
with workflow context and routes correctly inside Temporal workflows.

```python
from xians.agents.workflow_logs import XiansLogger
from xians.models.v1.configs import XiansOptions

# Enable server log upload by setting server_log_level
platform = await XiansPlatform.initialize(
    XiansOptions(
        server_url="https://api.agentri.ai",
        api_key="<your-api-key>",
        server_log_level="Information",   # enables server upload
        console_log_level="DEBUG",        # console output level
    )
)

# Use XiansLogger in your handlers (recommended)
logger = XiansLogger.for_name(__name__)
logger.log_info("Processing started")
logger.log_error("Something failed", exc=some_exception)
logger.log_warning(f"Retrying after {delay}s", exc=timeout_error)

# Check if a level is enabled (mirrors C# ILogger.IsEnabled)
import logging
if logger.is_enabled(logging.DEBUG):
    logger.log_debug(f"Expensive debug info: {compute_debug_data()}")
```

Standard Python `logging.info(...)` calls also work — `ApiLoggerHandler` catches
them on the root logger and uploads with context. But `XiansLogger` is recommended
because it attaches context data (`WorkflowId`, `Agent`, etc.) to every log
record for all handlers (console, file, third-party), not just the server upload.

### Logger usage pattern

| Where | Logger to use | Why |
|---|---|---|
| Your agent code (handlers, services) | `XiansLogger.for_name(__name__)` | Context stamping + C# API parity |
| SDK activity code (`message_activities.py`, etc.) | `XiansLogger.for_name(__name__)` | Dogfoods the SDK logger in the hot path |
| SDK infrastructure (`workflow_logs/` package) | `logging.getLogger(__name__)` | Avoids circular imports (XiansLogger is defined there) |
| Temporal workflow sandbox (`workflows.py`, `message_processor.py`) | `logging.getLogger(__name__)` / `workflow.logger` | Respects Temporal sandbox import restrictions |

All level methods accept an optional `exc` parameter for exception formatting
(mirrors C# where every `LogXxx` method accepts `Exception?`):

```python
logger.log_trace("msg", exc=error)
logger.log_debug("msg", exc=error)
logger.log_info("msg", exc=error)
logger.log_warning("msg", exc=error)
logger.log_error("msg", exc=error)
logger.log_critical("msg", exc=error)
```

## How It Works

### 1. Automatic Platform Integration

`XiansPlatform` manages the full logging lifecycle:

| Phase | What happens | Where |
|---|---|---|
| `XiansPlatform.initialize()` | Configures log levels, attaches `ApiLoggerHandler` to root Python logger | `platform.py` |
| `run_all()` → `_register_and_start_workers()` | Starts `LoggingServices` background upload thread | `platform.py` |
| Activity execution | `XiansContext` populated with workflow identity fields | `message_activity_workflow_logging.py` |
| Any log call via `XiansLogger` | `_get_context_data()` attaches `WorkflowId`, `Agent`, etc. as `extra` on `LogRecord` (mirrors C# `BeginScope`) | `xians_logger.py` |
| Any `logging.*()` call in handler | `ApiLoggerHandler` reads context from `XiansContext`, enqueues to `LoggingServices` | `api_logger_handler.py` |
| `run_all()` finally block | `LoggingServices.shutdown()` flushes remaining logs | `platform.py` |

### 2. XiansLogger (user-facing — mirrors `Logger<T>`)

- **Cached per type/name** — `XiansLogger.for_type(MyClass)` returns the same
  instance on repeated calls (`ConcurrentDictionary` in C#, `dict` + `Lock` in Python).
- **Per-call context scoping** — every log call reads `XiansContext` via
  `_get_context_data()` and attaches `WorkflowId`, `WorkflowRunId`, `WorkflowType`,
  `Agent`, and `ParticipantId` as `extra` on the Python `LogRecord`. This mirrors
  C# `Logger<T>.GetContextData()` + `BeginScope(contextData)`.
- **Workflow-safe routing** — inside Temporal workflows, delegates to
  `workflow.logger` (replay-safe) with context `extra`. Optionally dual-logs to
  the standard Python logger for console + server visibility.
- **Lazy logger initialization** — the underlying `logging.Logger` is created on
  first use via `_get_logger()`, matching C# `Lazy<ILogger>`.
- **`is_enabled(level)`** — checks whether a log level is enabled, mirroring
  C# `ILogger.IsEnabled(LogLevel)`.

### 3. ApiLoggerHandler (mirrors `ApiLoggerProvider / ApiLogger`)

- Python `logging.Handler` subclass attached to the root logger during platform init.
- At emit time: reads correlation fields from `XiansContext.safe_*()`, creates a
  `WorkflowLogRequest`, and enqueues to `LoggingServices`.
- Adds `traceId` / `spanId` when OpenTelemetry is active via shared helper
  `trace_utils.current_trace_context()` (same helper as `WorkflowLogEmitter`).
- Includes Temporal message re-classification (e.g. `ActivityFailureException` → Critical).

### 4. LoggingServices (mirrors `LoggingServices`)

- Global `queue.Queue` + background daemon thread.
- Batches up to 100 records (configurable) every 30 seconds (configurable).
- Retry tracking per log with max 3 attempts before dropping.
- Clean shutdown: flushes remaining queue synchronously.

### 5. LoggerFactory (mirrors `Common.Infrastructure.LoggerFactory`)

- `parse_log_level("INFO")` → `logging.INFO`
- `get_console_log_level()` / `get_server_log_level()` — env var → override → default.
- `configure_log_levels()` — programmatic override during platform init.
- `setup_root_logging()` — one-shot root config (console + API handler).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CONSOLE_LOG_LEVEL` | `DEBUG` | Minimum level for console output |
| `SERVER_LOG_LEVEL` | `ERROR` | Minimum level for server upload |
| `API_LOG_LEVEL` | *(none)* | Legacy fallback for `SERVER_LOG_LEVEL` |
| `WORKFLOW_LOG_TO_CONSOLE` | `true` | Dual-log workflow logs to console+server |

## Correlation Fields

Every log record sent to the server includes:

| Field | Source |
|---|---|
| `workflowId` | `activity.info().workflow_id` (canonical Temporal ID) |
| `workflowRunId` | `activity.info().workflow_run_id` |
| `workflowType` | `XiansContext.safe_workflow_type()` |
| `agent` | `XiansContext.safe_agent_name()` |
| `activation` | `XiansContext.safe_id_postfix()` (memo → parse from workflow ID) |
| `participantId` | `XiansContext.safe_participant_id()` |
| `tenantId` | `XiansContext.safe_tenant_id()` |
| `traceId` / `spanId` | OpenTelemetry span context (when instrumented) |

## Workflow Instance Separation (Auditing)

The Manager UI Auditing section lets you filter logs by agent, workflow type, and
specific workflow instance. Each distinct `workflowId` appears as a separate
entry in the "Select Workflow" dropdown.

### How `workflowId` format works

The Temporal workflow ID follows the pattern:

```
{tenantId}:{agentName}:{workflowName}[:{idPostfix}]
```

- **3 segments** (e.g. `default:My Agent:Supervisor Workflow`) — default activation
- **4 segments** (e.g. `default:My Agent:Supervisor Workflow:prod1`) — named activation

The 4th segment (`idPostfix`) is what differentiates multiple instances of the
same agent/workflow in the UI. It is assigned by the **server** when a **named
activation** is created for an agent whose definition has `activable: True`.

### Activation flow (required for per-instance separation)

The server controls the workflow ID. The Python worker listens for work on the
task queue and handles whichever workflow the server starts. To get separate
workflow instances with postfixes you **must go through the activation flow**:

| Step | Where | What happens |
|------|-------|-------------|
| 1. Upload definition | Python worker starts → `_upload_definitions()` | Definition with `activable: True` is uploaded to `POST /api/agent/definitions` |
| 2. Create activation | Manager UI → Activations section | Creates activation record in MongoDB with a name (e.g. "prod1") |
| 3. Activate | Manager UI → click "Activate" on the activation | Server calls `POST .../activate` which starts a **new** Temporal workflow with ID `{tenant}:{agent}:{workflow}:{activationName}` and memo `{idPostfix: "prod1"}` |
| 4. Send messages | Chat / Conversations for that activation | Messages are signaled to the specific workflow instance (4-segment ID) |

**Important:** If you start a conversation/run directly (not through an
activation), the server starts a **default** workflow with a 3-segment ID (no
postfix). Only the activation flow produces 4-segment IDs.

### C# vs Python `activable` defaults

| Workflow type | C# default | Python default | Notes |
|---|---|---|---|
| Built-in (conversational) | `false` | `true` | C# uses `false` because built-in workflows are "automatically activated upon invocation". Python defaults to `true` for activation support. |
| Custom | `true` | `true` | Both default to `true` |

The `activable` flag is configurable:

```python
conversational_wf = agent.define_builtin_workflow(
    name="Supervisor Workflow",
    activable=True,   # default; set False to match C# built-in behavior
)
```

### Requirements for per-instance log separation

1. **Agent definition must set `activable: True`** — the Python SDK does this
   by default in `define_builtin_workflow()` (configurable).
2. **Named activations must be created and activated** in the Manager UI (or
   via admin API). Each activation gets the activation name as `idPostfix`
   appended to the workflow ID.
3. **`idPostfix` propagation** — the workflow reads `idPostfix` from its memo
   (set by the server at activation start) and forwards it to the activity via
   `ProcessMessageActivityRequest.metadata`. The activity sets it in
   `XiansContext` so that all log records include the correct `activation` field.

### Context flow

```
Server activates "prod1" → starts Temporal workflow with:
  workflowId = "default:My Agent:Supervisor Workflow:prod1"
  memo = {"idPostfix": "prod1", "tenantId": "default", "agent": "My Agent", ...}
  taskQueue = "default:My Agent:Supervisor Workflow" (same queue, no postfix)

Python worker picks up the workflow on the shared task queue
  → BuiltinWorkflow.run() logs: id=...:prod1 idPostfix="prod1"
  → MessageProcessor reads memo, passes idPostfix in request.metadata
  → Activity: setup_message_activity_context() sets XiansContext.id_postfix
  → ApiLoggerHandler reads XiansContext.safe_id_postfix() at emit time
  → Log record: activation="prod1", workflowId="default:Agent:Workflow:prod1"
```

### Troubleshooting: "Select Workflow" only shows 3-segment IDs

If you only see `default:Agent:Workflow` (no postfix variants) in the Auditing
dropdown, check:

1. **Was the activation actually activated?** — Creating an activation record is
   not enough. You must click "Activate" in the Manager UI (or call
   `POST .../activate` via API) to start the Temporal workflow with the postfix.
2. **Check the Python worker logs** — on startup, the workflow logs:
   `Workflow started: id=... idPostfix=...`. If `idPostfix` is `None`, the
   server started the workflow without a postfix (default run, not activation).
3. **Check the definition upload** — the worker logs
   `Workflow definition: ... activable=True`. If `activable=False`, the server
   will skip this workflow during activation.
4. **Task queue match** — the worker logs `Started worker for ... on queue ...`.
   This must match the server's task queue (system-scoped: `{workflowType}`,
   tenant-scoped: `{tenantId}:{workflowType}`).

## Initialization (manual — advanced)

For advanced scenarios where you need to configure logging independently of
`XiansPlatform`, the components can be initialized manually:

```python
from xians.agents.workflow_logs import LoggingServices, WorkflowLogService
from xians.agents.workflow_logs.logger_factory import (
    configure_log_levels,
    parse_log_level,
    setup_root_logging,
)

# 1. Configure log levels
configure_log_levels(
    console_log_level=parse_log_level("DEBUG"),
    server_log_level=parse_log_level("Information"),
)

# 2. Attach ApiLoggerHandler to root logger
setup_root_logging(enable_api_logging=True)

# 3. Start background upload thread
log_service = WorkflowLogService(xians_client, min_server_log_level="Information")
LoggingServices.initialize(log_service)

# 4. On shutdown — flush remaining logs
LoggingServices.shutdown()
```

## C# Parity Reference

The Python `XiansLogger` mirrors C# `Logger<T>` / `XiansLogger<T>` method-for-method:

| C# (`Logger<T>`) | Python (`XiansLogger`) | Notes |
|---|---|---|
| `Logger<T>.For()` / `Logger.For(Type)` | `XiansLogger.for_type(cls)` / `XiansLogger.for_name(name)` | Cached instances |
| `ConcurrentDictionary<Type, Logger>` | `dict` + `threading.Lock` (double-check locking) | Same thread-safe caching pattern |
| `Lazy<ILogger>` | `_get_logger()` (creates on first use) | Deferred logger creation |
| `GetContextData()` | `_get_context_data()` | Reads `XiansContext.safe_*()` on every log call |
| `BeginScope(contextData)` | `extra=context_data` on Python `LogRecord` | Context attached to every record |
| `LogToWorkflowLogger(level, msg, exc, ctx)` | `_log_to_workflow_logger(level, msg, exc, ctx)` | Workflow.Logger + context scope |
| `LogToStandardLogger(level, msg, exc, ctx)` | `_log_to_standard_logger(level, msg, exc, ctx)` | Standard logger + context scope |
| `Workflow.InWorkflow` | `_in_workflow()` → `temporalio.workflow.in_workflow()` | Workflow detection |
| `ILogger.IsEnabled(LogLevel)` | `is_enabled(level)` | Level check |
| `LogTrace/Debug/Information/Warning/Error/Critical(msg, exc?)` | `log_trace/debug/info/information/warning/error/critical(msg, exc=None)` | All level methods accept optional exception |
| `ShouldLogWorkflowToConsole()` | `should_log_workflow_to_console()` | `WORKFLOW_LOG_TO_CONSOLE` env var |

### Context fields attached per log call

| C# field (`GetContextData`) | Python field (`_get_context_data`) | Source |
|---|---|---|
| `SafeWorkflowId` → `"WorkflowId"` | `safe_workflow_id()` → `"WorkflowId"` | `XiansContext` |
| `SafeWorkflowRunId` → `"WorkflowRunId"` | `_get_from_temporal_context("run_id")` → `"WorkflowRunId"` | `XiansContext` |
| `SafeWorkflowType` → `"WorkflowType"` | `safe_workflow_type()` → `"WorkflowType"` | `XiansContext` |
| `SafeAgentName` → `"Agent"` | `safe_agent_name()` → `"Agent"` | `XiansContext` |
| — | `safe_participant_id()` → `"ParticipantId"` | `XiansContext` (Python also includes participant) |

### Class hierarchy simplification

C# uses 6 types: `IXiansLogger`, `TypeBasedLoggerWrapper`, `Logger` (static),
`XiansLogger` (static), `XiansLogger<T>` (generic), `Logger<T>` (generic).
Python consolidates all of these into a single `XiansLogger` class with identical
runtime behavior. C# generics (`XiansLogger<T>`) map to Python string-based keys
via `XiansLogger.for_type(MyClass)`.

## Per-Activity Emitter (backward compat)

The `WorkflowLogEmitter` is still available for explicit per-activity batching.
It sends milestone logs (e.g. "Workflow message received", "User handler completed")
and routes failed uploads to the global `LoggingServices` queue as a fallback.
It uses the same `trace_utils.current_trace_context()` helper as `ApiLoggerHandler`
for OpenTelemetry `traceId` / `spanId` on emitted records.
