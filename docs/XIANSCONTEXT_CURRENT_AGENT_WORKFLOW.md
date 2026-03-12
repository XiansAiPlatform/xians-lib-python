# XiansContext - CurrentAgent & CurrentWorkflow

## Overview

The Python SDK mirrors the C# `XiansContext.CurrentAgent` and `XiansContext.CurrentWorkflow`
**properties** — accessed without parentheses, exactly like C#:

```python
# Python (mirrors C# exactly)
agent    = XiansContext.CurrentAgent
workflow = XiansContext.CurrentWorkflow

# Chain into sub-objects, just like C#:
# XiansContext.CurrentAgent.name
# XiansContext.CurrentWorkflow.workflow_type
```

```csharp
// C# equivalent
var agent    = XiansContext.CurrentAgent;
var workflow = XiansContext.CurrentWorkflow;

XiansContext.CurrentAgent.Knowledge.SearchAsync();
XiansContext.CurrentWorkflow.Schedules.Create();
```

This is achieved with a **metaclass** (`_XiansContextMeta`) that defines
`CurrentAgent` and `CurrentWorkflow` as `@property` on the class itself,
so they resolve on attribute access — no function call needed.

---

## How It Works

### Registration (Platform Startup)

When you register agents and workflows through the platform API:

```python
platform = await XiansPlatform.initialize(options)
agent = platform.agents.register(name="MyAgent")
wf = agent.define_builtin_workflow(name="Conversational")
```

Under the hood:

1. `AgentRegistration.__init__` → `XiansContext.register_agent("MyAgent", self)`
2. `XiansWorkflow.__init__` → `XiansContext.register_workflow("MyAgent:Conversational", self)`

### Runtime Context: Built-in vs Custom Workflows

**Built-in workflows (e.g. conversational)**  
When `MessageActivities.process_and_send_message` runs, it populates the
async-local context **before** invoking your handler:

```
set_workflow_id(request.workflow_id)      # e.g. "t1:MyAgent:Conversational:abc"
set_workflow_type(request.workflow_type)   # e.g. "MyAgent:Conversational"
set_agent_name("MyAgent")                 # extracted from workflow_type
set_tenant_id(request.tenant_id)
set_participant_id(request.participant_id)
set_authorization(request.authorization)
set_request_id(request.request_id)
```

All of these are **cleared** in the `finally` block to prevent cross-activity leaking.

**Custom workflows**  
Custom workflow activities (e.g. `ContextInspectorWorkflow` running `inspect_context`)
do **not** go through `process_and_send_message`. The SDK still resolves identity and
some context by reading from **Temporal’s execution context** and the **workflow ID**:

- **CurrentAgent / CurrentWorkflow** — Resolved from `activity.info().workflow_type` (or
  `workflow.info().workflow_type` in workflow code), then registry lookup. No manual
  context setup required.
- **workflow_id** — From `activity.info().workflow_id` (or contextvar when set).
- **tenant_id** — From contextvar, or **parsed from workflow ID** (first segment before `:`).
- **id_postfix** — From contextvar, or **parsed from workflow ID** (4th segment, if present).
- **participant_id**, **request_id** — Only set by `process_and_send_message` (inbound
  message payload). They remain **null** in custom workflow activities; this matches C#.

### Property Resolution

When you access `XiansContext.CurrentAgent`, the metaclass property runs:

1. **Test override** → `_current_agent_override` (async-local) or `_static_current_agent_override`
2. **Derive agent name** → from explicit `set_agent_name()` → from **Temporal context** (`activity.info().workflow_type` or `workflow.info().workflow_type` prefix) → from workflow ID
3. **Registry lookup** → `_agent_registry[agent_name]`

When you access `XiansContext.CurrentWorkflow`:

1. **Derive workflow type** → from explicit `set_workflow_type()` → from **Temporal context** (`activity.info().workflow_type` / `workflow.info().workflow_type`) → from workflow ID (`"tenant:agent:workflow:postfix"` → `"agent:workflow"`)
2. **Registry lookup** → `_workflow_registry[workflow_type]`

---

## Usage in Handlers and Custom Workflow Activities

**Inside a built-in workflow handler** (e.g. chat, data, webhook):

```python
from xians.agents.core import XiansContext

async def my_chat_handler(ctx) -> None:
    agent = XiansContext.CurrentAgent
    print(agent.name)
    workflow = XiansContext.CurrentWorkflow
    print(workflow.workflow_type)
    # tenant_id, participant_id, request_id are also set by MessageActivities
```

**Inside a custom workflow activity** (e.g. an activity run by a custom Temporal workflow):

```python
from xians.agents.core import XiansContext

@activity.defn(name="InspectContext")
async def inspect_context(query: str) -> str:
    # CurrentAgent / CurrentWorkflow resolve from Temporal context — no setup needed
    agent = XiansContext.CurrentAgent
    workflow = XiansContext.CurrentWorkflow
    tenant_id = XiansContext.get_tenant_id()   # from context or parsed from workflow_id
    workflow_id = XiansContext.get_workflow_id()
    # participant_id and request_id are null unless set by your workflow/activity input
```

`CurrentAgent` and `CurrentWorkflow` resolve from Temporal’s `activity.info()` / `workflow.info()` when the async-local context was not set (e.g. in custom workflows). `get_tenant_id()` and `get_workflow_id()` use the same Temporal context and workflow ID parsing where applicable.

---

## Context Getters (Tenant, Participant, Request, Workflow ID, IdPostfix)

Resolution order matches the C# XiansContext behavior:

| Getter | Resolution order | Notes |
|--------|------------------|--------|
| `get_workflow_id()` | Contextvar → **Temporal** (`activity.info().workflow_id` / `workflow.info().workflow_id`) | Always available in workflow/activity. |
| `get_tenant_id()` | Contextvar → **Workflow ID** (first segment, e.g. `default:Agent:Workflow` → `default`) | Set by MessageActivities in built-in; otherwise parsed from workflow ID. |
| `get_id_postfix()` | Contextvar → **Workflow ID** (4th segment, timestamp suffix stripped) | Null if workflow ID has fewer than 4 segments. |
| `get_participant_id()` | Contextvar only | Set only by `process_and_send_message`; **null** in custom workflow activities. |
| `get_request_id()` | Contextvar only | Set only by `process_and_send_message`; **null** in custom workflow activities. |

So in a **custom workflow activity**, `get_tenant_id()` and `get_workflow_id()` can still return values (from Temporal context and workflow ID parsing). `get_participant_id()` and `get_request_id()` remain null unless your workflow explicitly passes and sets them (e.g. via activity input and `XiansContext.set_participant_id` / `set_request_id`).

---

## Error Behavior

| Scenario | Exception |
|---|---|
| No workflow/activity context, no test override | `RuntimeError` |
| Agent name resolved but not in registry | `KeyError` |
| No workflow type can be derived | `RuntimeError` |
| Workflow type resolved but not in registry | `KeyError` |

These match the C# behavior where `CurrentAgent` / `CurrentWorkflow`
throw `InvalidOperationException` or `KeyNotFoundException`.

---

## Test Overrides

For unit tests without Temporal, bypass context resolution entirely:

```python
from xians.agents.core import XiansContext

class FakeAgent:
    name = "TestAgent"

fake = FakeAgent()
XiansContext.set_current_agent_for_tests(fake)

try:
    assert XiansContext.CurrentAgent is fake
    assert XiansContext.CurrentAgent.name == "TestAgent"
finally:
    XiansContext.clear_current_agent_for_tests()
```

This mirrors `SetCurrentAgentForTests` / `ClearCurrentAgentForTests` from C#.

---

## Implementation Detail: Metaclass

Python's `@staticmethod` cannot be a `@property`. To support
parentheses-free access on the class itself (`XiansContext.CurrentAgent`),
we use a metaclass:

```python
class _XiansContextMeta(type):
    @property
    def CurrentAgent(cls) -> object:
        # resolution logic ...

    @property
    def CurrentWorkflow(cls) -> object:
        # resolution logic ...

class XiansContext(metaclass=_XiansContextMeta):
    ...
```

The metaclass defines `CurrentAgent` and `CurrentWorkflow` as **class-level
properties**, so attribute access on the class (not an instance) triggers
the property getter. This gives us identical ergonomics to C# static properties.

---

## C# → Python Mapping Summary

| C# | Python |
|---|---|
| `XiansContext.CurrentAgent` | `XiansContext.CurrentAgent` |
| `XiansContext.CurrentWorkflow` | `XiansContext.CurrentWorkflow` |
| `XiansContext.CurrentAgent.Name` | `XiansContext.CurrentAgent.name` |
| `XiansContext.CurrentAgent.Knowledge.SearchAsync()` | Not yet implemented (see [SDK_ACCESS_PATTERNS.md](SDK_ACCESS_PATTERNS.md)) |
| `XiansContext.CurrentAgent.Schedules.Create()` (C# has Schedules on Agent) | Not yet implemented (see [SDK_ACCESS_PATTERNS.md](SDK_ACCESS_PATTERNS.md)) |
| `SetCurrentAgentForTests(agent)` | `set_current_agent_for_tests(agent)` |
| `ClearCurrentAgentForTests()` | `clear_current_agent_for_tests()` |
| `XiansContext.TenantId` | `XiansContext.get_tenant_id()` |
| `XiansContext.WorkflowId` | `XiansContext.get_workflow_id()` |
| `XiansContext.GetParticipantId()` | `XiansContext.get_participant_id()` |
| `XiansContext.GetRequestId()` | `XiansContext.get_request_id()` |
| `XiansContext.GetIdPostfix()` | `XiansContext.get_id_postfix()` |
| `XiansContext.InWorkflow` | `XiansContext.in_workflow()` |
| `XiansContext.InActivity` | `XiansContext.in_activity()` |
| `XiansContext.InWorkflowOrActivity` | `XiansContext.in_workflow_or_activity()` |

Context resolution (tenant from workflow ID, workflow type from Temporal context, etc.) is aligned with C# so that `CurrentAgent`, `CurrentWorkflow`, and the getters behave the same in both SDKs.
