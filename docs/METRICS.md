# Metrics & Usage Tracking

Track everything your agents do—from LLM token usage to business outcomes—with zero configuration required.

This document covers the Python SDK implementation of the Metrics feature, mirroring the C# `Xians.Lib.Agents.Metrics` module and the [XiansAi.Docs concepts/metrics](docs/concepts/metrics.md) walkthrough.

---

## Choose Your Starting Point

The metrics system has two entry points depending on where you're working:

### 📨 In Message Listeners? Use `context.metrics`

When handling user messages, the context already knows everything:

```python
async def my_chat_handler(context):
    await context.metrics \
        .with_metric("tokens", "total", 150, "tokens") \
        .report_async()

workflow.on_user_chat_message(my_chat_handler)
```

### ⚙️ In Custom Workflows? Use `XiansContext.Metrics`

For workflows and activities, grab context from the Xians runtime:

```python
from xians.agents.core import XiansContext

# In a workflow or activity
await XiansContext.Metrics \
    .with_metric("workflow", "started", 1, "count") \
    .report_async()
```

---

## Beyond the Basics

Want more control? Chain these fluent methods:

```python
await context.metrics \
    .with_custom_identifier(f"msg-{message_id}") \
    .with_metadata("version", "2.1.0") \
    .with_request_id("trace-123") \
    .with_metrics(
        ("tokens", "prompt", 45, "tokens"),
        ("tokens", "completion", 105, "tokens"),
    ) \
    .report_async()
```

**Optional:** Only add `.for_model("gpt-4")` when tracking model-specific costs or performance.

---

## Why Track Metrics?

Agent work spans **technical** (tokens, API calls), **business** (approvals, documents), and **operational** (HITL tasks) layers. Xians auto-captures context (tenant, user, workflow) so you track what matters.

---

## Automatic Context Population

Every metric report automatically includes:

| Field | Auto-Populated From | Purpose |
|-------|---------------------|---------|
| `tenant_id` | `XiansContext.safe_tenant_id()` | Multi-tenant isolation |
| `participant_id` | `XiansContext.safe_participant_id()` | User attribution |
| `workflow_id` | `XiansContext.safe_workflow_id()` | Session tracking |
| `agent_name` | `XiansContext.safe_agent_name()` or agent name | Agent attribution |
| `activation_name` | `XiansContext.safe_id_postfix()` | Workflow type |

**No setup required.** Call it from anywhere in your workflow or activity.

---

## Common Patterns

### Track LLM Token Usage

```python
response = await call_llm(prompt)

await context.metrics \
    .for_model("gpt-4") \
    .with_metrics(
        ("tokens", "prompt", response.prompt_tokens, "tokens"),
        ("tokens", "completion", response.completion_tokens, "tokens"),
        ("tokens", "total", response.total_tokens, "tokens"),
    ) \
    .report_async()
```

### Track Business Outcomes

```python
await context.metrics \
    .with_metrics(
        ("approvals", "submitted", 1, "count"),
        ("documents", "generated", 1, "count"),
        ("emails", "sent", 3, "count"),
    ) \
    .report_async()
```

### Track Performance

```python
import time

start = time.perf_counter()
result = await process_data(input)
elapsed_ms = (time.perf_counter() - start) * 1000

await context.metrics \
    .with_metrics(
        ("performance", "processing_time", elapsed_ms, "ms"),
        ("performance", "records_processed", len(result), "count"),
    ) \
    .report_async()
```

### Link to External Systems

Use custom identifiers to correlate metrics with your external systems:

```python
await context.metrics \
    .for_model("gpt-4") \
    .with_custom_identifier(f"msg-{message_id}") \
    .with_metric("tokens", "total", 150, "tokens") \
    .report_async()
```

---

## Fine-Tune When Needed

Need to override auto-populated values? Chain any of these:

- `.with_tenant_id(str)` - Override tenant
- `.with_user_id(str)` - Override participant/user
- `.with_workflow_id(str)` - Override workflow
- `.with_request_id(str)` - Set request correlation ID
- `.from_source(str)` - Override source identifier

**Example:**

```python
await XiansContext.Metrics \
    .with_tenant_id("custom-tenant") \
    .with_user_id("admin-override") \
    .with_metric("admin", "action", 1, "count") \
    .report_async()
```

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  User Code                                                       │
│  context.metrics / XiansContext.Metrics                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  ContextAwareUsageReportBuilder                                  │
│  - Fluent API (with_metric, for_model, etc.)                     │
│  - Auto-populates from XiansContext / message context            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  MetricsCollection                                              │
│  - report_async(request)                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  MetricsExecutor                                                 │
│  - In workflow: execute_activity("ReportUsage", payload)         │
│  - In activity: MetricsService.report_async(request)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────────────────┐
│  UsageActivities        │   │  MetricsService                      │
│  (Temporal activity)    │   │  (Direct HTTP)                       │
│  - report_usage()       │   │  - report_async()                   │
└────────────┬────────────┘   └────────────────┬────────────────────┘
             │                                  │
             └──────────────┬───────────────────┘
                            ▼
             ┌──────────────────────────────────┐
             │  XiansServerClient               │
             │  POST /api/agent/usage/report    │
             └──────────────────────────────────┘
```

### Context-Aware Execution

The metrics system uses the **ContextAwareActivityExecutor** pattern (matching C#):

- **Inside a Temporal workflow**: Metrics are reported via the `ReportUsage` activity. This keeps the workflow deterministic—no direct HTTP calls from workflow code.
- **Inside an activity or outside Temporal**: Metrics are reported directly via `MetricsService` (HTTP call to the Xians server).

You call the same API everywhere. The system chooses the right approach automatically.

### Data Model

**MetricValue** (single metric):

- `category` - e.g., "tokens", "approvals", "performance"
- `type` - e.g., "total", "prompt", "submitted"
- `value` - numeric value (float)
- `unit` - e.g., "tokens", "count", "ms"

**UsageReportRequest** (full report):

- `tenant_id`, `participant_id`, `workflow_id`, `request_id`
- `workflow_type`, `model`, `custom_identifier`
- `agent_name`, `activation_name`
- `metrics` - list of MetricValue
- `metadata` - optional dict

---

## Best Practices

✅ **Track early and often** - Metrics are cheap, insights are valuable  
✅ **Use meaningful categories** - "tokens", "approvals", "emails", not "metric1"  
✅ **Include units** - "tokens", "count", "ms", "usd"  
✅ **Link to business value** - Track what matters to your users  
✅ **Use custom identifiers** - Correlate with your external systems  

❌ **Don't track PII** - Metrics are for aggregation, not user data  
❌ **Don't track secrets** - Never include API keys or credentials  
❌ **Don't over-specify** - Let auto-population handle context fields  

---

## Summary

Metrics in Xians Python SDK are:

- **Automatic**: Context population with zero configuration
- **Flexible**: Track any metric with any label
- **Universal**: Same API in workflows, activities, and message handlers
- **Smart**: Workflow-aware, determinism-aware (activity vs direct HTTP)

Just call `.with_metric()` and `.report_async()`. Everything else is handled for you.
