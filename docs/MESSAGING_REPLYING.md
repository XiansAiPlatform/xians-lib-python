# Replying to User Messages

Built-in workflows in Xians provide a powerful messaging system that allows your agents to listen for incoming messages and respond to users naturally. This guide covers everything you need to know about handling user messages and crafting responses in the Python SDK.

## Two Flavors of Messaging

Xians provides two distinct mechanisms for communicating with users:

### 1. Replying to User Messages (This Document)

When users send messages to your agent, you respond using **message context** methods available in your message listeners:

```python
async def my_chat_handler(context: UserMessageContext) -> None:
    await context.reply_async("I received your message!")

conversational_workflow.on_user_chat_message(my_chat_handler)
```

**Key characteristics:**

- **User-initiated**: Responding to incoming messages
- **Context-aware**: Automatic participant ID, thread continuity, scope inheritance
- **Conversational**: Interactive back-and-forth exchanges
- **Access method**: `context.reply_async()`, `context.send_data_async()`, `context.send_handoff_async()`

### 2. Proactive Messaging

When your agent needs to initiate conversations from background workflows, scheduled tasks, or events, use **XiansContext.Messaging**:

```python
from xians.agents.core import XiansContext

# In any workflow or activity
await XiansContext.Messaging.send_chat_async(
    text="Your order has shipped!",
    participant_id="user-123",
)
```

Full documentation: [Proactive Messaging](./MESSAGING_PROACTIVE.md)

---

## Overview

When you define a built-in workflow (like a Conversational workflow), you can register **message listeners** that are triggered when users send messages to your agent. These listeners receive a rich context object that contains the incoming message details and provides methods to respond.

## Message Listeners

### Listening to Chat Messages

The most common type of message is a chat message. Register a listener using `on_user_chat_message`:

```python
from xians.agents.messaging import UserMessageContext

async def my_chat_handler(context: UserMessageContext) -> None:
    user_message = context.message.text
    await context.reply_async(f"You said: {user_message}")

conversational_workflow = xians_agent.workflows.define_builtin(name="Conversational")
conversational_workflow.on_user_chat_message(my_chat_handler)
```

### Listening to Data Messages

For structured data messages, use `on_user_data_message`:

```python
async def my_data_handler(context: UserMessageContext) -> None:
    data = context.message.data
    await context.reply_async("Data received and processed!")

conversational_workflow.on_user_data_message(my_data_handler)
```

### Listening to File Uploads

For file uploads (base64-encoded files sent with `type: "File"`), use `on_file_upload`:

```python
async def my_file_handler(context: UserMessageContext) -> None:
    file_data = context.message.data
    await context.reply_async("File received!")

conversational_workflow.on_file_upload(my_file_handler)
```

Full documentation: [File Upload Messaging](./MESSAGING_FILEUPLOAD.md)

## Accessing Message Properties

The `context.message` property gives you access to all incoming message details:

```python
async def my_chat_handler(context: UserMessageContext) -> None:
    # Message content
    text = context.message.text
    data = context.message.data

    # User and conversation context
    participant_id = context.message.participant_id
    thread_id = context.message.thread_id
    request_id = context.message.request_id

    # Additional context
    scope = context.message.scope
    hint = context.message.hint
    tenant_id = context.message.tenant_id

    # Authorization (if applicable)
    authorization = context.message.authorization
```

### Message Properties Reference

| Property | Type | Description |
|----------|------|-------------|
| `text` | `str` | The text content of the message |
| `data` | `Any` | Structured data associated with the message |
| `participant_id` | `str` | Unique identifier for the conversation participant |
| `request_id` | `str` | Unique identifier for this specific message request |
| `thread_id` | `str` | Thread identifier for conversation threading |
| `scope` | `str` | Optional scope for organizing messages into topics |
| `hint` | `str` | Optional hint for message handling |
| `tenant_id` | `str` | Tenant identifier (for multi-tenant applications) |
| `authorization` | `str` | Authorization token if provided |
| `message_type` | `str` | The type of message (chat, data, file, webhook, heartbeat) |

## Message Types

When responding to users, there are several distinct message types:

| Type | Purpose | Method | Use Case |
|------|---------|--------|----------|
| **Chat** | Standard agent-user conversations | `reply_async()` | Text-based communication and typical conversational interactions |
| **Data** | Passing structured data between parties | `send_data_async()` | Sending structured data objects; data is the primary content |
| **Reasoning** | Streaming agent thinking steps | `send_reasoning_async()` | Show intermediate reasoning/planning steps |
| **Tool** | Streaming tool execution steps | `send_tool_exec_async()` | Show which tools are being invoked |
| **Handoff** | Transfer user to a different workflow | `send_handoff_async()` | Routing to specialized agents |
| **Heartbeat** | Frontend liveness check | *(handled automatically)* | Verifying an agent worker is available |

### Heartbeat Messages

Heartbeat is a special message type used by the frontend (or platform) to verify an agent worker is running and reachable. **No user handler is invoked.** When a heartbeat arrives:

1. The workflow extracts the tenant ID from the workflow ID.
2. On success it responds immediately with a **Data** message: `{ "available": true }` with `origin: "heartbeat"`.
3. If tenant extraction fails but a fallback tenant can be derived (first segment of `workflowId`), a **Data** message with `{ "available": false, "reason": "configuration_error" }` is sent so the UI can distinguish a misconfiguration from a genuine worker timeout.
4. If no fallback tenant can be determined, no response is sent at all (the UI treats silence as "worker unreachable").

Developers do **not** need to register a handler for heartbeat—it is processed entirely by the SDK's `MessageProcessor`.

## Responding to Users

### Simple Text Replies

```python
async def my_handler(context: UserMessageContext) -> None:
    await context.reply_async("Hello! How can I help you today?")
```

### Replies with Data

Send both text and structured data together using the optional `data` parameter:

```python
async def my_handler(context: UserMessageContext) -> None:
    result = {
        "status": "Success",
        "processed_items": 42,
    }
    await context.reply_async("Processing complete!", data=result)
```

### Data-Focused Responses

When the primary response is structured data, use `send_data_async`:

```python
async def my_handler(context: UserMessageContext) -> None:
    analytics = {
        "users_active": 150,
        "events_today": 1200,
    }
    await context.send_data_async(data=analytics, content="Here are today's analytics")
```

### Skipping Responses

Sometimes you want to process a message silently without sending a response:

```python
async def my_handler(context: UserMessageContext) -> None:
    context.skip_response = True
    # Process internally but don't reply
```

## Conversation History

Retrieve past messages for the current conversation:

```python
async def my_handler(context: UserMessageContext) -> None:
    history = await context.get_chat_history_async(page=1, page_size=50)
    for msg in history:
        print(f"[{msg.direction}] {msg.text}")
```

## Handoff

Transfer the conversation to another workflow:

```python
async def my_handler(context: UserMessageContext) -> None:
    await context.send_handoff_async(
        target_workflow_id="tenant:Agent:OtherWorkflow:postfix",
        message="Transferring you to a specialist",
        user_message="Please wait while I connect you...",
    )
```

The `user_message` parameter sends a message to the user before the handoff occurs.

## Task ID Retrieval

Get the last HITL (Human-in-the-Loop) task ID:

```python
async def my_handler(context: UserMessageContext) -> None:
    task_id = await context.get_last_task_id_async()
    if task_id:
        print(f"Last task: {task_id}")
```

## Metrics Tracking

Track usage metrics from within message handlers:

```python
async def my_handler(context: UserMessageContext) -> None:
    response = await call_llm(context.message.text)
    await context.reply_async(response.text)

    await (context.metrics
        .for_model("gpt-4")
        .with_metric("tokens", "total", response.total_tokens, "tokens")
        .report_async())
```

## Related

- [Proactive Messaging](./MESSAGING_PROACTIVE.md) — Send messages without a user context
- [Message Progress](./MESSAGING_PROGRESS.md) — Reasoning and tool execution messages
- [File Upload Messaging](./MESSAGING_FILEUPLOAD.md) — Handle file uploads
- [SDK Access Patterns](./SDK_ACCESS_PATTERNS.md) — Full API reference
