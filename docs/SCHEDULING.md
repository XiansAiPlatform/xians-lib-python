# Scheduling

## Temporal-backed cron jobs for your agents

Build recurring workflow executions without running your own cron daemon.
`xians.agents.scheduling` mirrors the C# `Xians.Lib.Agents.Scheduling`
feature: Temporal handles the scheduling, retries, multi-tenant isolation,
and durable execution, while your workflows remain plain `@workflow.defn`
classes.

Use it for:

- Daily / weekly / monthly reports
- Periodic polling (email inbox, webhooks, price feeds)
- Batch maintenance jobs
- Any workflow that should run on a clock

---

## Architecture

The Python implementation mirrors the C# `Xians.Lib.Agents.Scheduling`
layout almost one-to-one:

```
agents/scheduling/
├── models/
│   ├── activity_requests.py     # Dataclasses passed between workflow and activities
│   └── exceptions.py             # ScheduleNotFoundError, ScheduleAlreadyExistsError, ...
├── schedule_id_helper.py         # Builds tenant:agent:idPostfix:name IDs
├── schedule_builder.py           # Fluent builder (with_cron_schedule, …, create_async)
├── schedule_extensions.py        # Fluent helpers (daily, hourly, every_minutes, …)
├── schedule_collection.py        # Agent-level entry point (create, get, pause, …)
└── xians_schedule.py             # Wrapper around Temporal ScheduleHandle

temporal_workflows/v1/
└── schedule_activities.py        # Temporal activities used from inside workflows
```

### Layered design

| Layer | Class | Responsibility |
|-------|-------|----------------|
| **Models** | `CreateCronScheduleRequest`, `CreateIntervalScheduleRequest`, `ScheduleExistsRequest`, … | Serializable activity payloads (dataclasses) |
| **ID helper** | `ScheduleIdHelper` | Builds `{tenantId}:{agent}:{idPostfix}:{scheduleName}` schedule IDs and `{tenantId}:{workflowType}:{idPostfix}` workflow IDs |
| **Builder** | `ScheduleBuilder` | Fluent configuration (spec + workflow args + policies) and creation (`create_async`, `create_if_not_exists_async`, `recreate_async`) |
| **Extensions** | `schedule_extensions` | High-level cron/interval shorthands attached to `ScheduleBuilder` (`daily`, `hourly`, `every_minutes`, `skip_if_running`, …) |
| **Collection** | `ScheduleCollection` | One per agent: `create`, `get_async`, `exists_async`, `pause_async`, `unpause_async`, `trigger_async`, `delete_async` |
| **Handle wrapper** | `XiansSchedule` | Async surface over `ScheduleHandle` (`describe_async`, `pause_async`, `update_async`, `backfill_async`, …) |
| **Activities** | `ScheduleActivities` | Temporal activities auto-registered on every worker so workflows can create/manage schedules deterministically |

### Context-aware execution

`ScheduleBuilder` routes creation calls based on the current execution
context — the same pattern the rest of the SDK uses:

- **Inside a Temporal workflow** → dispatches to `ScheduleActivities.*` so
  the workflow stays deterministic.
- **Inside a Temporal activity or a plain async function** → calls the
  Temporal client directly via the platform's active connection.

This matches the C# `ScheduleBuilder.CreateViaActivitiesAsync` /
`CreateViaTemporalClientAsync` split.

---

## Quick start

### 1. Register an agent and a workflow

```python
from xians.interfaces.v1 import XiansPlatform, XiansAgentRegistration
from temporalio import workflow

@workflow.defn(name="ReportingAgent:DailyReport")
class DailyReportWorkflow:
    @workflow.run
    async def run(self, report_type: str = "summary") -> None:
        workflow.logger.info(f"Running daily report: {report_type}")
        # ... your report logic ...

platform = XiansPlatform()
agent = platform.agents.register(
    XiansAgentRegistration(name="ReportingAgent")
)
agent.define_custom_workflow(DailyReportWorkflow)
```

### 2. Create a schedule

```python
schedule = await (
    agent.schedules
    .create("daily-report", DailyReportWorkflow)
    .daily(hour=9, minute=0)                # cron "0 9 * * *"
    .with_input("summary")                   # becomes workflow.run("summary")
    .skip_if_running()                       # recommended overlap policy
    .create_if_not_exists_async()            # idempotent
)

print(schedule.id)   # "default:ReportingAgent::daily-report"
```

### 3. Manage it

```python
# Pause / resume
await agent.schedules.pause_async("daily-report", note="Weekend freeze")
await agent.schedules.unpause_async("daily-report")

# Trigger immediately (in addition to the normal cadence)
await agent.schedules.trigger_async("daily-report")

# Describe
details = await schedule.describe_async()
print(details.info.next_action_times[:5])

# Delete
await agent.schedules.delete_async("daily-report")
```

---

## Scheduling options

### Time-based (cron shortcuts)

```python
.create("s", Wf).daily(hour=9, minute=0)             # every day at 09:00
.create("s", Wf).hourly(minute=30)                    # every hour at :30
.create("s", Wf).weekly(day_of_week=1, hour=8)        # Mondays 08:00 (0=Sun ... 6=Sat)
.create("s", Wf).monthly(day_of_month=1, hour=9)      # 1st of month 09:00
.create("s", Wf).weekdays(hour=9, minute=0)           # Mon–Fri 09:00
```

### Interval-based

```python
.create("s", Wf).every_seconds(30)
.create("s", Wf).every_minutes(5)
.create("s", Wf).every_hours(2)
.create("s", Wf).every_days(3)
```

### Custom cron expression

```python
.create("s", Wf).with_cron_schedule("0 9 * * 1-5", timezone="America/New_York")
```

Format: `{minute} {hour} {day-of-month} {month} {day-of-week}`.

### One-time (calendar) schedule

```python
from datetime import datetime

.create("s", Wf).with_calendar_schedule(
    datetime(2026, 12, 31, 23, 59, 0),
    timezone="UTC",
)
```

### Fully custom `ScheduleSpec`

```python
from temporalio.client import ScheduleSpec

.create("s", Wf).with_schedule_spec(ScheduleSpec(...))
```

---

## Workflow inputs, memo, and search attributes

```python
from temporalio.common import RetryPolicy
from datetime import timedelta

await (
    agent.schedules
    .create("process-orders", ProcessOrdersWorkflow)
    .every_minutes(15)
    .with_input(batch_size=100, priority="normal")   # positional or kwargs
    .with_memo({"owner": "ops-team", "version": "2"})
    .with_retry_policy(RetryPolicy(maximum_attempts=3))
    .with_timeout(timedelta(minutes=30))
    .skip_if_running()
    .create_if_not_exists_async()
)
```

All runs of the schedule receive the same memo and workflow arguments until
the schedule is updated or recreated.

---

## Overlap policies

Choose what happens when the next scheduled time arrives before the
previous execution has finished:

| Helper | Temporal policy | Semantics |
|--------|-----------------|-----------|
| `.skip_if_running()` | `SKIP` | Skip the new run. Recommended default. |
| `.allow_overlap()` | `ALLOW_ALL` | Run concurrently (no synchronization). |
| `.buffer_one()` | `BUFFER_ONE` | Queue at most one pending run. |
| `.cancel_other()` | `CANCEL_OTHER` | Cancel the running workflow and start a new one. |
| `.terminate_other()` | `TERMINATE_OTHER` | Force-terminate the running workflow. |

---

## Creation methods

```python
# Strict: fails if the schedule ID already exists
await builder.create_async()

# Idempotent: returns the existing schedule if present
await builder.create_if_not_exists_async()

# Replace: delete existing (if any), then create fresh
await builder.recreate_async()
```

Use `create_if_not_exists_async()` for most real-world deployments — it is
safe to call on every startup.

---

## Multi-tenant isolation

Schedule and workflow IDs are built automatically:

```
schedule id  : {tenantId}:{agentName}:{idPostfix}:{scheduleName}
workflow id  : {tenantId}:{workflowType}:{idPostfix}
```

- `tenantId` — from `XiansContext.get_tenant_id()` or the agent's configured tenant.
- `agentName` — the registered agent name.
- `idPostfix` — optional run-scoping (e.g. one schedule per user). Resolved from
  the workflow context when omitted.
- `scheduleName` — your stable business identifier.

Two tenants can therefore share the same `scheduleName` without collisions.

### Per-user / per-thread scopes

```python
# One schedule per user:
await (
    agent.schedules
    .create("reminder", ReminderWorkflow, id_postfix=user_id)
    .daily(hour=9)
    .create_if_not_exists_async()
)

await agent.schedules.get_async("reminder", id_postfix=user_id)
```

---

## Using schedules from inside a workflow

The builder detects workflow context and dispatches to `ScheduleActivities`
automatically, keeping the workflow deterministic:

```python
from temporalio import workflow
from xians.agents.core import XiansContext

@workflow.defn(name="Onboarding:Setup")
class OnboardingWorkflow:
    @workflow.run
    async def run(self, user_id: str) -> None:
        agent = XiansContext.CurrentAgent
        await (
            agent.schedules
            .create("welcome-email", WelcomeEmailWorkflow, id_postfix=user_id)
            .daily(hour=9)
            .with_input(user_id)
            .create_if_not_exists_async()
        )
```

The activities are registered on every worker by `XiansPlatform`, so no
extra configuration is required.

> **Note**: Only cron and interval schedules are supported from inside
> workflows. Calendar and raw `ScheduleSpec` schedules must be created
> from outside a workflow (e.g. startup code or an activity).

---

## Memo payload

Every schedule-triggered workflow execution carries a memo with:

| Key | Value |
|-----|-------|
| `tenantId` | Effective tenant ID |
| `agent` | Registered agent name |
| `userId` | Current participant ID (or `""`) |
| `idPostfix` | Resolved idPostfix (or `""`) |
| `systemScoped` | Whether the agent is system-scoped |

User-supplied `.with_memo({...})` entries are merged on top.

## Standard search attributes

The same four keys are **also** attached as typed `Keyword` search attributes
on both the schedule itself and every workflow execution it starts, so
operators can filter in the Temporal UI:

| Key | Type | Meaning |
|-----|------|---------|
| `tenantId` | Keyword | Tenant the schedule was created in |
| `agent` | Keyword | Registered agent name |
| `userId` | Keyword | Current participant ID (or `""`) |
| `idPostfix` | Keyword | Resolved idPostfix (or `""`) |

Mirrors C# `WorkflowMetadataResolver.BuildSearchAttributes` — the four
`StandardMetadataKeys`. They are attached automatically on every
`create_async` / `create_if_not_exists_async` call; `.with_typed_search_attributes(...)`
entries are merged on top (user-provided keys win on conflicts).

> **One-time setup required.** These four keys must be pre-registered on
> your Temporal namespace (same requirement as the C# library). With the
> default `temporal` CLI: `temporal operator search-attribute create --name tenantId --type Keyword`
> (repeat for `agent`, `userId`, `idPostfix`). Without this, Temporal will
> reject schedule creation with an error that names the missing key.

---

## Error handling

```python
from xians.agents.scheduling import (
    InvalidScheduleSpecError,
    ScheduleAlreadyExistsError,
    ScheduleNotFoundError,
)

try:
    await builder.create_async()
except ScheduleAlreadyExistsError as ex:
    logger.warning("schedule %s already exists", ex.schedule_id)
except InvalidScheduleSpecError:
    ...

try:
    await agent.schedules.get_async("missing")
except ScheduleNotFoundError:
    ...
```

---

## Best practices

- Prefer `create_if_not_exists_async()` so deployments are idempotent.
- Default to `skip_if_running()` to avoid unbounded concurrency.
- Keep workflow arguments small and JSON-serializable — they are
  re-transmitted on every run.
- Use `id_postfix` to scope per-user/per-tenant schedules.
- Delete or recreate schedules when you change their cron/interval — Temporal
  does **not** pick up code changes to an existing schedule's spec.
- Tag schedules with `.with_memo(...)` or typed search attributes for easy
  listing and filtering in Temporal UI.

---

## API reference (summary)

### `ScheduleCollection` (on every `AgentRegistration`)

- `create(schedule_name, workflow_type_or_class, id_postfix=None) -> ScheduleBuilder`
- `get_async(name, id_postfix=None) -> XiansSchedule`
- `exists_async(name, id_postfix=None) -> bool`
- `pause_async(name, id_postfix=None, note=None)`
- `unpause_async(name, id_postfix=None, note=None)`
- `trigger_async(name, id_postfix=None)`
- `delete_async(name, id_postfix=None)`

### `ScheduleBuilder`

Spec helpers: `with_cron_schedule`, `with_interval_schedule`,
`with_calendar_schedule`, `with_schedule_spec`.

Fluent shorthands: `daily`, `hourly`, `weekly`, `monthly`, `weekdays`,
`every_seconds`, `every_minutes`, `every_hours`, `every_days`,
`skip_if_running`, `allow_overlap`, `buffer_one`, `cancel_other`,
`terminate_other`.

Configuration: `with_input`, `with_memo`, `with_typed_search_attributes`,
`with_retry_policy`, `with_timeout`, `with_schedule_policy`,
`with_overlap_policy`, `start_paused`.

Creation: `create_async`, `create_if_not_exists_async`, `recreate_async`.

### `XiansSchedule`

- `describe_async() -> ScheduleDescription`
- `pause_async(note=None)` / `unpause_async(note=None)`
- `trigger_async()`
- `update_async(updater)`
- `backfill_async(backfills)`
- `delete_async()`
- `get_handle() -> ScheduleHandle`  (escape hatch)

---

## C# Python API parity

The tables below enumerate every public member of the C#
`Xians.Lib.Agents.Scheduling` namespace and the equivalent in
`xians.agents.scheduling`. Names follow each language's idioms —
PascalCase + `Async` suffix in C#, snake_case + `_async` suffix in
Python — but the semantics are identical.

Legend: `✅` fully-implemented, one-to-one semantics.  `➕` Python-only
addition documented in the concepts doc.  `➖` deliberately omitted
(see note).

### `ScheduleCollection`

| C# (member) | Python (member) | Status | Notes |
|-------------|-----------------|--------|-------|
| `Create<TWorkflow>(scheduleName)` | `create(schedule_name, workflow_class)` | ✅ | Python accepts either a `@workflow.defn`-decorated class or a workflow-type string. |
| `Create(scheduleName, workflowType, idPostfix?)` | `create(schedule_name, workflow_type, id_postfix=None)` | ✅ | Same method signature is reused for both overloads. |
| `GetAsync(scheduleName)` / `GetAsync(scheduleName, idPostfix?)` | `get_async(schedule_name, id_postfix=None)` | ✅ | Raises `ScheduleNotFoundError` when absent. |
| `ExistsAsync(scheduleName)` / `ExistsAsync(scheduleName, idPostfix?)` | `exists_async(schedule_name, id_postfix=None)` | ✅ | Uses a direct `describe` probe so missing schedules produce no warnings. |
| `PauseAsync(scheduleName, note?)` / `PauseAsync(scheduleName, idPostfix?, note?)` | `pause_async(schedule_name, id_postfix=None, note=None)` | ✅ | |
| `UnpauseAsync(scheduleName, note?)` / `UnpauseAsync(scheduleName, idPostfix?, note?)` | `unpause_async(schedule_name, id_postfix=None, note=None)` | ✅ | |
| `TriggerAsync(scheduleName)` / `TriggerAsync(scheduleName, idPostfix?)` | `trigger_async(schedule_name, id_postfix=None)` | ✅ | |
| `DeleteAsync(scheduleName)` / `DeleteAsync(scheduleName, idPostfix?)` | `delete_async(schedule_name, id_postfix=None)` | ✅ | Raises `ScheduleNotFoundError` when absent. |

### `ScheduleBuilder` — spec helpers

| C# | Python | Status |
|----|--------|--------|
| `WithCronSchedule(cronExpression, timezone?)` | `with_cron_schedule(cron_expression, timezone=None)` | ✅ |
| `WithIntervalSchedule(interval, offset?)` | `with_interval_schedule(interval, offset=None)` | ✅ |
| `WithCalendarSchedule(scheduledTime, timezone?)` | `with_calendar_schedule(scheduled_time, timezone=None)` | ✅ |
| `WithScheduleSpec(spec)` | `with_schedule_spec(spec)` | ✅ |

### `ScheduleBuilder` — configuration

| C# | Python | Status |
|----|--------|--------|
| `WithInput(params object[] args)` | `with_input(*args)` | ✅ |
| `WithMemo(Dictionary<string, object>)` | `with_memo(dict[str, Any])` | ✅ |
| `WithTypedSearchAttributes(SearchAttributeCollection?)` | `with_typed_search_attributes(search_attributes)` | ✅ |
| `WithRetryPolicy(RetryPolicy)` | `with_retry_policy(retry_policy)` | ✅ |
| `WithTimeout(TimeSpan)` | `with_timeout(timeout: timedelta)` | ✅ |
| `WithSchedulePolicy(SchedulePolicy)` | `with_schedule_policy(policy)` | ✅ |
| `WithOverlapPolicy(ScheduleOverlapPolicy)` | `with_overlap_policy(overlap_policy)` | ✅ |
| `StartPaused(paused=true, note?)` | `start_paused(paused=True, note=None)` | ✅ |

### `ScheduleBuilder` — creation

| C# | Python | Status |
|----|--------|--------|
| `CreateAsync()` | `create_async()` | ✅ |
| `CreateIfNotExistsAsync()` | `create_if_not_exists_async()` | ✅ |
| `RecreateAsync()` (documented pattern) | `recreate_async()` | ➕ Python implements the documented `Recreate` pattern directly (delete-if-exists, then `CreateAsync`). |

### `ScheduleExtensions` (fluent shorthands)

All C# extension methods are attached as regular methods on
`ScheduleBuilder` via `schedule_extensions.py`, so the fluent chain
works the same way in both languages.

| C# extension | Python method | Status |
|--------------|---------------|--------|
| `Daily(hour, minute=0, timezone?)` | `daily(hour, minute=0, timezone=None)` | ✅ |
| `Hourly(minute=0)` | `hourly(minute=0)` | ✅ |
| `Weekly(DayOfWeek, hour, minute=0, timezone?)` | `weekly(day_of_week, hour, minute=0, timezone=None)` | ✅ Uses int `0=Sunday…6=Saturday` (matches C# `DayOfWeek` enum values). |
| `Monthly(dayOfMonth, hour, minute=0, timezone?)` | `monthly(day_of_month, hour, minute=0, timezone=None)` | ✅ |
| `Weekdays(hour, minute=0, timezone?)` | `weekdays(hour, minute=0, timezone=None)` | ✅ |
| `EverySeconds(seconds)` | `every_seconds(seconds)` | ✅ |
| `EveryMinutes(minutes)` | `every_minutes(minutes)` | ✅ |
| `EveryHours(hours)` | `every_hours(hours)` | ✅ |
| `EveryDays(days, hour=0, minute=0, timezone?)` | `every_days(days, hour=0, minute=0, timezone=None)` | ✅ Multi-day intervals ignore `hour`/`minute`, same as C#. |
| `AllowOverlap()` | `allow_overlap()` | ✅ |
| `SkipIfRunning()` | `skip_if_running()` | ✅ |
| `BufferOne()` | `buffer_one()` | ✅ |
| `CancelOther()` | `cancel_other()` | ✅ |
| `TerminateOther()` | `terminate_other()` | ✅ |

### `XiansSchedule` (handle wrapper)

| C# | Python | Status |
|----|--------|--------|
| `Id` | `id` | ✅ |
| `DescribeAsync()` | `describe_async()` | ✅ |
| `PauseAsync(note?)` | `pause_async(note=None)` | ✅ |
| `UnpauseAsync(note?)` | `unpause_async(note=None)` | ✅ |
| `TriggerAsync()` | `trigger_async()` | ✅ |
| `UpdateAsync(updater)` | `update_async(updater)` | ✅ Takes the same Temporal `(ScheduleUpdateInput) -> ScheduleUpdate` callable. |
| `DeleteAsync()` | `delete_async()` | ✅ |
| `BackfillAsync(backfills)` | `backfill_async(backfills)` | ✅ |
| `GetHandle()` | `get_handle()` | ✅ |

### `ScheduleIdHelper`

| C# | Python | Status |
|----|--------|--------|
| `BuildFullScheduleId(tenantId, agentName, idPostfix, scheduleName)` | `ScheduleIdHelper.build_full_schedule_id(...)` | ✅ Identical pattern: `{tenantId}:{agentName}[:{idPostfix}]:{scheduleName}`. |
| `BuildFullWorkflowId(tenantId, workflowType, idPostfix)` | `ScheduleIdHelper.build_full_workflow_id(...)` | ✅ |

### Exceptions

| C# | Python | Status |
|----|--------|--------|
| `ScheduleAlreadyExistsException` | `ScheduleAlreadyExistsError` | ✅ Both carry `schedule_id` / `ScheduleId`. |
| `ScheduleNotFoundException` | `ScheduleNotFoundError` | ✅ |
| `InvalidScheduleSpecException` | `InvalidScheduleSpecError` | ✅ |

### Activities (in-workflow dispatch)

| C# activity class | Python activity class | Status |
|-------------------|----------------------|--------|
| `ScheduleActivities.CreateScheduleIfNotExists` | `ScheduleActivities.create_schedule_if_not_exists` | ✅ |
| `ScheduleActivities.CreateIntervalScheduleIfNotExists` | `ScheduleActivities.create_interval_schedule_if_not_exists` | ✅ |
| `ScheduleActivities.ScheduleExists` | `ScheduleActivities.schedule_exists` | ✅ |
| `ScheduleActivities.DeleteSchedule` | `ScheduleActivities.delete_schedule` | ✅ |
| `ScheduleActivities.PauseSchedule` | `ScheduleActivities.pause_schedule` | ✅ |
| `ScheduleActivities.ResumeSchedule` | `ScheduleActivities.resume_schedule` | ✅ |
| `ScheduleActivities.TriggerSchedule` | `ScheduleActivities.trigger_schedule` | ✅ |

### Context-aware routing parity

| Behaviour | C# source | Python source | Status |
|-----------|-----------|---------------|--------|
| Workflow-context detection → use activities | `Workflow.InWorkflow` check in `ScheduleBuilder.CreateAsync` | `XiansContext.in_workflow()` check in `ScheduleBuilder.create_async` | ✅ |
| `idPostfix` resolution (explicit → context → fallback) | `GetEffectiveIdPostfixForSchedule` | `ScheduleBuilder._resolve_effective_id_postfix` | ✅ |
| Tenant resolution (system-scoped vs tenant-scoped) | `GetEffectiveTenantId` | `ScheduleBuilder._effective_tenant_id` | ✅ |
| Memo payload (`tenantId`, `agent`, `userId`, `idPostfix`, `systemScoped`) | `GetMemo` | `ScheduleBuilder._build_memo` | ✅ |
| Search attributes on scheduled workflow action | `ScheduleActionStartWorkflow { TypedSearchAttributes = … }` | `ScheduleActionStartWorkflow(typed_search_attributes=…)` | ✅ |
| Search attributes on the schedule itself | Post-create `handle.UpdateAsync` | `client.create_schedule(..., search_attributes=…)` | ✅ Equivalent; Python SDK lets us do it in one call. |

### Minor intentional differences

| Area | C# | Python | Rationale |
|------|----|--------|-----------|
| Fluent configuration | C# extension methods (`this ScheduleBuilder`) | Regular methods attached to `ScheduleBuilder` via `schedule_extensions.py` monkey-patch | Python has no C#-style extension method syntax; the module patches `ScheduleBuilder` at import time so the same fluent chain is preserved. |
| `Weekly` parameter type | `DayOfWeek` enum (`Sunday…Saturday`) | `int` (`0=Sunday…6=Saturday`) | Avoids introducing a duplicate enum; same underlying cron value. |
| Activity `ScheduleActivityOptions.GetStandardOptions` | C# helper with retry/timeout defaults | Inlined `timedelta(minutes=2)` start-to-close timeout | Same 2-minute start-to-close default as C#. |
| Search-attribute marshalling across activity boundary | `WorkflowMetadataResolver.ExtractToSerializableDictionary` | `ScheduleBuilder._serialize_search_attributes` | Temporal Python can't serialize `TypedSearchAttributes` over the activity boundary, so we flatten to a `dict[str, Any]` (same approach C# uses). |

### What `XiansAi.Docs/concepts/scheduling.md` describes vs. Python

The public concepts documentation lists every user-facing capability.
Every one is available in the Python library:

| Concept (from `scheduling.md`) | Python equivalent | Status |
|--------------------------------|-------------------|--------|
| Self-scheduling workflows (example `DailyReportWorkflow`) | Same pattern with `XiansContext.CurrentAgent.schedules.create(...)` inside a `@workflow.defn` | ✅ |
| Time-based shortcuts (`Daily`, `Hourly`, `Weekdays`, `Weekly`, `Monthly`) | `daily`, `hourly`, `weekdays`, `weekly`, `monthly` | ✅ |
| Interval shortcuts (`EverySeconds`, `EveryMinutes`, `EveryHours`, `EveryDays`) | `every_seconds`, `every_minutes`, `every_hours`, `every_days` | ✅ |
| Cron expressions (`WithCronSchedule`) | `with_cron_schedule` | ✅ |
| One-time calendar schedule (`WithCalendarSchedule`) | `with_calendar_schedule` | ✅ |
| Overlap policies (`SkipIfRunning` / `AllowOverlap` / `BufferOne` / `CancelOther` / `TerminateOther`) | `skip_if_running`, `allow_overlap`, `buffer_one`, `cancel_other`, `terminate_other` | ✅ |
| Creation modes (`CreateIfNotExistsAsync`, `CreateAsync`, `RecreateAsync`) | `create_if_not_exists_async`, `create_async`, `recreate_async` | ✅ |
| Lifecycle (`PauseAsync`, `UnpauseAsync`, `TriggerAsync`, `DescribeAsync`, `DeleteAsync`, `UpdateAsync`, `BackfillAsync`, `GetHandle`) | Same names in snake_case on `XiansSchedule` + `ScheduleCollection` | ✅ |
| Starting paused (`StartPaused`) | `start_paused` | ✅ |
| Custom `idPostfix` (`Create("name", type, idPostfix: "x")`) | `create("name", type, id_postfix="x")` | ✅ |
| Low-level Temporal escape hatch (`GetHandle`) | `get_handle()` | ✅ |
| Exceptions (`ScheduleAlreadyExistsException` / `ScheduleNotFoundException` / `InvalidScheduleSpecException`) | `ScheduleAlreadyExistsError`, `ScheduleNotFoundError`, `InvalidScheduleSpecError` | ✅ |
| Multi-tenant isolation (`{tenantId}:{agentName}:{idPostfix}:{scheduleName}`) | Same ID pattern produced by `ScheduleIdHelper` | ✅ |

**Bottom line**: every method and behaviour documented in the C# library
and `XiansAi.Docs/concepts/scheduling.md` has a direct, behaviour-equivalent
counterpart in `xians-lib-python`.
