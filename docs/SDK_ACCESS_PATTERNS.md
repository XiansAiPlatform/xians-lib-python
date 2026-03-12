# SDK Access Patterns (Python)

This document describes the **four SDK access patterns** from the Xians SDK design and how they are implemented and used in the **Python agent library** (`xians-lib-python`). It aligns with the concept doc [SDK Access Patterns](https://docs.xians.ai/concepts/sdk-patterns) and compares with the C# implementation (`Xians.Lib`) where relevant.

---

## Quick reference

| Access Pattern | Purpose | Available In | Python status |
|----------------|---------|--------------|---------------|
| **UserMessageContext** | Message-specific operations | Message handlers only | ✅ Implemented |
| **CurrentAgent** | Agent-level data (knowledge, documents) | All workflows | ⚠️ Partial |
| **CurrentWorkflow** | Workflow-level operations (schedules, identity) | All workflows | ⚠️ Partial |
| **XiansContext** | Cross-cutting (messaging, A2A, sub-workflows, registry) | All workflows | ⚠️ Partial |

---

## 1. UserMessageContext — Message-specific operations

**When:** Inside built-in workflow message handlers only (chat, data, file, webhook).  
**Use for:** Replying to the user, conversation history, message metadata, handoff.

### Python API (implemented)

The handler receives a `UserMessageContext` instance (e.g. `context`). All operations are available.

| Operation | Python | Notes |
|-----------|--------|--------|
| Message metadata | `context.message.participant_id`, `.thread_id`, `.workflow_id`, `.tenant_id`, `.request_id`, `.scope`, `.hint`, `.data`, `.text`, `.message_type` | Matches C# `context.Message` |
| Reply (chat) | `await context.reply_async("text", data=None)` | C# `ReplyAsync(text)` / `ReplyAsync(text, data)` |
| Send data | `await context.send_data_async(data, content=None)` | C# `SendDataAsync(data, content)` |
| Send reasoning | `await context.send_reasoning_async(data, content=None)` | C# `SendReasoningAsync(data, content)` |
| Send tool exec | `await context.send_tool_exec_async(data, content=None)` | C# `SendToolExecAsync(data, content)` |
| Chat history | `await context.get_chat_history_async(page=1, page_size=50)` | C# `GetChatHistoryAsync(page, pageSize)` |
| Last task ID | `await context.get_last_task_id_async()` | C# `GetLastTaskIdAsync()` |
| Handoff | `await context.send_handoff_async(target_workflow_id, message=..., data=..., user_message=...)` | C# `SendHandoffAsync(...)` |
| Skip response | `context.skip_response = True` | C# `SkipResponse` |

### How to use in the agent

**Built-in workflow — chat handler:**

```python
from xians.agents.messaging import UserMessageContext

async def my_chat_handler(context: UserMessageContext) -> None:
    user_id = context.message.participant_id
    thread_id = context.message.thread_id

    # Reply to this message
    await context.reply_async("Here is the response.")

    # Optional: get conversation history
    history = await context.get_chat_history_async(page=1, page_size=50)

    # Optional: hand off to another workflow
    await context.send_handoff_async(
        target_workflow_id="tenant:Agent:OtherWorkflow:postfix",
        message="Handing off",
    )
```

**Registration:**

```python
workflow.on_user_chat_message(my_chat_handler)
```

**C# comparison:** The Python `UserMessageContext` matches the C# type: same semantics for reply, history, handoff, and message properties. Implemented correctly.

---

## 2. CurrentAgent — Agent-level data

**When:** Any workflow (built-in or custom).  
**Use for:** Knowledge search, document storage, agent metadata.

### Python API

| Operation | C# | Python | Status |
|----------|-----|--------|--------|
| Agent identity | `XiansContext.CurrentAgent.Name` | `XiansContext.CurrentAgent.name` | ✅ |
| Knowledge search | `await XiansContext.CurrentAgent.Knowledge.SearchAsync("query")` | Not exposed on agent | ❌ Gap |
| Documents save | `await XiansContext.CurrentAgent.Documents.SaveAsync(document)` | Not exposed on agent | ❌ Gap |
| Documents query | `await XiansContext.CurrentAgent.Documents.QueryAsync(...)` | Not exposed on agent | ❌ Gap |
| Schedules (C# on Agent) | `XiansContext.CurrentAgent.Schedules.Create(...)` | Not exposed on agent | ❌ Gap |

**Note:** The concept doc shows **CurrentWorkflow.Schedules**; in C# the implementation is **CurrentAgent.Schedules**. The Python lib does not yet expose Knowledge, Documents, or Schedules on `CurrentAgent`.

### How to use in the agent (what exists today)

**Access current agent (e.g. in a handler or custom activity):**

```python
from xians.agents.core import XiansContext

async def my_handler(context) -> None:
    agent = XiansContext.CurrentAgent
    print(agent.name)  # e.g. "MyAgent"
    # agent.knowledge / agent.documents / agent.schedules not yet in Python
```

**Workaround for knowledge/documents:** The HTTP API exists on `XiansServerClient` (used internally by the platform). To use knowledge or documents from an agent today you would need to call the server client directly (e.g. via a shared client from your platform or a custom activity that has access to it). A future release should add `CurrentAgent.Knowledge` and `CurrentAgent.Documents` facades to match C#.

**C# comparison:** C# exposes `CurrentAgent.Knowledge`, `CurrentAgent.Documents`, `CurrentAgent.Schedules`, and `CurrentAgent.Tasks`. Python currently only exposes `CurrentAgent` (the registration object) with `name` and `system_scoped`; no Knowledge/Documents/Schedules/Tasks facades yet.

---

## 3. CurrentWorkflow — Workflow-level operations

**When:** Any workflow (built-in or custom).  
**Use for:** Schedules (per concept doc), workflow identity, task queue.

### Python API

| Operation | C# | Python | Status |
|----------|-----|--------|--------|
| Workflow type | `XiansContext.CurrentWorkflow.WorkflowType` | `XiansContext.CurrentWorkflow.workflow_type` | ✅ |
| Workflow ID (runtime) | `XiansContext.CurrentWorkflow.WorkflowId` or `XiansContext.WorkflowId` | `XiansContext.get_workflow_id()` | ✅ (on context) |
| Task queue | `XiansContext.CurrentWorkflow.TaskQueue` | Not on CurrentWorkflow; use `build_task_queue_name(workflow_type, system_scoped, tenant_id)` from worker_runner | ⚠️ Different |
| Schedules (concept doc) | `XiansContext.CurrentWorkflow.Schedules!.Create(...)` | Not implemented | ❌ Gap |

In C#, **Schedules** are on **XiansAgent** (`CurrentAgent.Schedules`), not on `XiansWorkflow`. The concept doc shows `CurrentWorkflow.Schedules`; the C# codebase uses `CurrentAgent.Schedules`. Python has no Schedules API yet.

### How to use in the agent

**Workflow identity and context:**

```python
from xians.agents.core import XiansContext

async def in_handler_or_activity() -> None:
    workflow = XiansContext.CurrentWorkflow
    workflow_type = workflow.workflow_type  # e.g. "MyAgent:Conversational"
    workflow_id = XiansContext.get_workflow_id()  # runtime ID from Temporal/context
    tenant_id = XiansContext.get_tenant_id()
```

**Task queue:** In Python the task queue is built at worker registration time via `build_task_queue_name()`. There is no `CurrentWorkflow.task_queue` property; you can derive the same name with `build_task_queue_name(XiansContext.CurrentWorkflow.workflow_type, XiansContext.CurrentWorkflow.system_scoped, XiansContext.get_tenant_id())` if needed.

**C# comparison:** CurrentWorkflow in Python matches for workflow type and registration; WorkflowId is on XiansContext. Schedules and TaskQueue exposure differ as above.

---

## 4. XiansContext — Cross-cutting operations

**When:** Any workflow (built-in or custom).  
**Use for:** Proactive messaging, A2A, sub-workflows, agent/workflow registry.

### Python API

| Operation | C# | Python | Status |
|----------|-----|--------|--------|
| CurrentAgent | `XiansContext.CurrentAgent` | `XiansContext.CurrentAgent` | ✅ |
| CurrentWorkflow | `XiansContext.CurrentWorkflow` | `XiansContext.CurrentWorkflow` | ✅ |
| TenantId | `XiansContext.TenantId` | `XiansContext.get_tenant_id()` | ✅ |
| WorkflowId | `XiansContext.WorkflowId` | `XiansContext.get_workflow_id()` | ✅ |
| GetAgent | `XiansContext.GetAgent(name)` | `XiansContext.get_agent(name)` | ✅ |
| GetWorkflow | `XiansContext.GetWorkflow(workflowType)` | `XiansContext.get_workflow(workflow_type)` | ✅ |
| GetAllAgents | `XiansContext.GetAllAgents()` | `XiansContext.get_all_agents()` | ✅ |
| GetAllWorkflows | `XiansContext.GetAllWorkflows()` | `XiansContext.get_all_workflows()` | ✅ |
| Proactive messaging | `await XiansContext.Messaging.SendChatAsync(participantId, text)` | No XiansContext.Messaging facade | ❌ Gap |
| A2A | `await XiansContext.A2A.SendChatAsync(targetWorkflow, message)` | No XiansContext.A2A | ❌ Gap |
| Start sub-workflow | `await XiansContext.Workflows.StartAsync<T>(...)` | Use `AgentClient` from platform (e.g. `platform.client().invoke(...)`) with workflow_id/task_queue | ⚠️ Different |

### How to use in the agent

**Context and registry (implemented):**

```python
from xians.agents.core import XiansContext

# Any workflow or activity
tenant_id = XiansContext.get_tenant_id()
workflow_id = XiansContext.get_workflow_id()
participant_id = XiansContext.get_participant_id()  # set in message handlers only
request_id = XiansContext.get_request_id()

# Discover agents and workflows
agent = XiansContext.get_agent("MyAgent")
workflow = XiansContext.get_workflow("MyAgent:Conversational")
all_agents = XiansContext.get_all_agents()
all_workflows = XiansContext.get_all_workflows()

# Build IDs
wf_type = XiansContext.build_workflow_type("MyAgent", "Conversational")
wf_id = XiansContext.build_workflow_id(tenant_id, "MyAgent", "Conversational", id_postfix="conv-1")
```

**Proactive messaging (not yet on XiansContext):** In C# you call `XiansContext.Messaging.SendChatAsync(participantId, "Your order shipped!")`. In Python there is no central `XiansContext.Messaging`; messaging is done via `UserMessageContext` (reply in a handler) or via the low-level `MessageService` used inside the SDK. To send proactive messages from a custom workflow you would need access to a `MessageService` and to build a `SendMessageRequest` with workflow/participant/tenant from context. A future facade would align this with C#.

**A2A (not yet on XiansContext):** In C# you use `XiansContext.A2A.SendChatAsync(targetWorkflow, new A2AMessage { Text = "..." })`. In Python there is no A2A facade. You would need to start or signal the target workflow (e.g. via `AgentClient`) and pass the message as input/signal. A future A2A helper would match C#.

**Sub-workflows:** In Python, start workflows via the Temporal client. The platform exposes `platform.client()` returning an `AgentClient` after `run_all()` (or after connecting). Example:

```python
# After platform.run_all() or connect_temporal()
client = platform.client()
wf_id = XiansContext.build_workflow_id(
    XiansContext.get_tenant_id(), "MyAgent", "NotificationWorkflow",
    id_postfix="notify-123"
)
task_queue = build_task_queue_name("MyAgent:NotificationWorkflow", system_scoped=False, tenant_id=XiansContext.get_tenant_id())
await client.invoke(wf_id, task_queue, request, workflow_type="MyAgent:NotificationWorkflow")
```

There is no `XiansContext.Workflows.StartAsync`-style API; you use `AgentClient` and context helpers to build IDs and task queues.

**C# comparison:** Registry, tenant, workflow ID, and ID building are aligned. Messaging, A2A, and sub-workflow helpers are either missing or use a different entry point (AgentClient) in Python.

---

## Summary: implementation status

| Pattern | Python | C# | Gaps / notes |
|--------|--------|-----|----------------|
| **UserMessageContext** | Full | Full | Aligned. |
| **CurrentAgent** | Name only | Name, Knowledge, Documents, Schedules, Tasks | Python: add Knowledge, Documents, Schedules (and optionally Tasks) on agent. |
| **CurrentWorkflow** | workflow_type, registration | WorkflowType, WorkflowId, TaskQueue, (Schedules on Agent in C#) | Python: WorkflowId via context; TaskQueue via helper; no Schedules. |
| **XiansContext** | Context + registry + ID helpers | + Messaging, A2A, Workflows | Python: no Messaging/A2A/Workflows facades; use MessageService and AgentClient where needed. |

---

## Design philosophy (from concept doc)

**Explicit ownership:**

- **UserMessageContext** owns reply and conversation operations.
- **Agent** owns knowledge and documents (and in C#, schedules).
- **Workflow** owns workflow identity (and in the doc, schedules — in C# schedules are on the agent).
- **XiansContext** orchestrates messaging, A2A, sub-workflows, and registry.

The Python SDK follows the same ownership model where the APIs exist; the gaps are the missing facades (Knowledge, Documents, Schedules, Messaging, A2A, Workflows) rather than a different design.

---

## See also

- [XIANSCONTEXT_CURRENT_AGENT_WORKFLOW.md](XIANSCONTEXT_CURRENT_AGENT_WORKFLOW.md) — How `CurrentAgent` and `CurrentWorkflow` resolve and how to use them in handlers and custom workflows.
- [SDK Access Patterns](https://docs.xians.ai/concepts/sdk-patterns) (XiansAi.Docs) — Canonical pattern list and C# examples.
