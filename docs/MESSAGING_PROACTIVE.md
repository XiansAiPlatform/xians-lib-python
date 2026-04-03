# Proactive Messaging

Proactive messaging allows agents to initiate conversations with users from any workflow or activity, without needing a user message to reply to. This is the Python equivalent of C# `XiansContext.Messaging`.

## Overview

While `UserMessageContext` is used to **reply** to incoming messages, proactive messaging is used when the agent needs to **initiate** communication — for example, sending notifications, alerts, background task updates, or scheduled messages.

## XiansContext.Messaging

The primary interface for proactive messaging is `XiansContext.Messaging`, which provides a convenient facade that automatically resolves the participant ID from context when available.

### Sending Chat Messages

```python
from xians.agents.core import XiansContext

# Inside any workflow or activity
await XiansContext.Messaging.send_chat_async(
    text="Your order has shipped!",
    participant_id="user-123",
)
```

When called from within a message handler (where participant ID is in context), you can omit `participant_id`:

```python
await XiansContext.Messaging.send_chat_async(
    text="Processing your request in the background...",
)
```

### Sending Data Messages

```python
await XiansContext.Messaging.send_data_async(
    text="Order update",
    data={"order_id": "ORD-123", "status": "shipped", "tracking": "TRK-456"},
    participant_id="user-123",
)
```

### Sending as a Different Workflow

Send messages that appear to come from a different workflow (useful for background workers that want messages to appear in the main conversation):

```python
# Chat message as a different workflow
await XiansContext.Messaging.send_chat_as_workflow_async(
    builtin_workflow_name="Conversational",
    text="Content discovered!",
    participant_id="user-123",
)

# Data message as a different workflow
await XiansContext.Messaging.send_data_as_workflow_async(
    builtin_workflow_name="Conversational",
    text="Discovery results",
    data={"items_found": 5},
    participant_id="user-123",
)
```

### Sending as the Supervisor Workflow

Convenience methods for impersonating the Supervisor Workflow:

```python
await XiansContext.Messaging.send_chat_as_supervisor_async(
    text="Task completed successfully!",
    participant_id="user-123",
)

await XiansContext.Messaging.send_data_as_supervisor_async(
    text="Task results",
    data={"completed": True, "duration_ms": 1500},
    participant_id="user-123",
)
```

### Reasoning and Tool Messages via Supervisor

```python
await XiansContext.Messaging.send_reasoning_as_supervisor_async(
    text="Analyzing the user's request...",
    participant_id="user-123",
)

await XiansContext.Messaging.send_tool_call_as_supervisor_async(
    text="search_knowledge_base(query='best practices')",
    participant_id="user-123",
)
```

## UserMessaging (Low-Level API)

For more control, use `UserMessaging` directly. This is the lower-level API that `MessagingHelper` wraps:

```python
from xians.agents.messaging import UserMessaging

# Send a chat message
await UserMessaging.send_chat_async(
    participant_id="user-123",
    text="Hello from the agent!",
    scope="notifications",
)

# Send a data message
await UserMessaging.send_data_async(
    participant_id="user-123",
    text="Order update",
    data={"status": "shipped"},
)

# Send as a different workflow
await UserMessaging.send_chat_as_workflow_async(
    builtin_workflow_name="Conversational",
    participant_id="user-123",
    text="Background task completed!",
)

# Send reasoning/tool messages
await UserMessaging.send_reasoning_async(
    builtin_workflow_name="Conversational",
    participant_id="user-123",
    text="Thinking about the problem...",
)

await UserMessaging.send_tool_call_async(
    builtin_workflow_name="Conversational",
    participant_id="user-123",
    text="execute_search(query='...')",
)

# Get last task ID
task_id = await UserMessaging.get_last_task_id_async(
    participant_id="user-123",
    scope="support",
)
```

## API Reference

### MessagingHelper (via XiansContext.Messaging)

All methods support optional `participant_id`. If omitted, the participant ID is resolved from `XiansContext.get_participant_id()`.

| Method | Description |
|--------|-------------|
| `send_chat_async(text, data?, scope?, hint?, task_id?, participant_id?)` | Send a chat message |
| `send_data_async(text, data, scope?, hint?, task_id?, participant_id?)` | Send a data message |
| `send_chat_as_workflow_async(builtin_workflow_name, text, data?, ...)` | Chat as another workflow |
| `send_data_as_workflow_async(builtin_workflow_name, text, data, ...)` | Data as another workflow |
| `send_chat_as_supervisor_async(text, data?, ...)` | Chat as Supervisor Workflow |
| `send_data_as_supervisor_async(text, data, ...)` | Data as Supervisor Workflow |
| `send_reasoning_as_supervisor_async(text, data?, ...)` | Reasoning as Supervisor |
| `send_tool_call_as_supervisor_async(text, data?, ...)` | Tool call as Supervisor |

### UserMessaging (Low-Level)

All methods require explicit `participant_id`.

| Method | Description |
|--------|-------------|
| `send_chat_async(participant_id, text, data?, scope?, hint?, task_id?)` | Send a chat message |
| `send_data_async(participant_id, text, data, scope?, hint?, task_id?)` | Send a data message |
| `send_chat_as_workflow_async(builtin_workflow_name, participant_id, text, ...)` | Chat as another workflow |
| `send_data_as_workflow_async(builtin_workflow_name, participant_id, text, data, ...)` | Data as another workflow |
| `send_reasoning_async(builtin_workflow_name, participant_id, text, ...)` | Reasoning message |
| `send_tool_call_async(builtin_workflow_name, participant_id, text, ...)` | Tool call message |
| `get_last_task_id_async(participant_id, scope?)` | Get last HITL task ID |

## How It Works

Proactive messaging is context-aware and works differently depending on where it's called:

- **In a Temporal workflow**: Messages are sent via `Workflow.execute_activity("SendMessage", ...)` for determinism. A new `request_id` is generated using `Workflow.uuid4()`.
- **In a Temporal activity**: Messages are sent directly via `MessageService` HTTP calls. A new `request_id` is generated using `uuid.uuid4()`.

All proactive messages have `origin="agent-initiated"` to distinguish them from reply messages.

## Common Patterns

### Background Task Notifications

```python
# In a custom workflow activity
async def process_long_task(context: UserMessageContext) -> None:
    context.skip_response = True  # Don't auto-reply

    # Start background processing...
    await XiansContext.Messaging.send_chat_async(
        text="Starting your analysis. I'll notify you when it's done.",
    )

    result = await run_analysis()

    await XiansContext.Messaging.send_data_async(
        text="Analysis complete!",
        data=result,
    )
```

### Scheduled Notifications

```python
# In a scheduled workflow activity
from xians.agents.messaging import UserMessaging

async def send_daily_summary(participant_id: str, summary: dict) -> None:
    await UserMessaging.send_data_async(
        participant_id=participant_id,
        text="Here's your daily summary",
        data=summary,
        scope="daily-summary",
    )
```

## C# Comparison

| C# | Python | Notes |
|----|--------|-------|
| `XiansContext.Messaging.SendChatAsync(text)` | `await XiansContext.Messaging.send_chat_async(text)` | Identical semantics |
| `XiansContext.Messaging.SendDataAsync(text, data)` | `await XiansContext.Messaging.send_data_async(text, data)` | Identical semantics |
| `XiansContext.Messaging.SendChatAsWorkflowAsync(name, text)` | `await XiansContext.Messaging.send_chat_as_workflow_async(name, text)` | Identical semantics |
| `UserMessaging.SendChatAsync(pid, text)` | `await UserMessaging.send_chat_async(pid, text)` | Identical semantics |

## Related

- [Replying to User Messages](./MESSAGING_REPLYING.md) — Reply to incoming messages
- [Message Progress](./MESSAGING_PROGRESS.md) — Reasoning and tool execution messages
- [SDK Access Patterns](./SDK_ACCESS_PATTERNS.md) — Full API reference
