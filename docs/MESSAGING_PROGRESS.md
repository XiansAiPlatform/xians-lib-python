# Message Progress

Between the moment a user sends a message and when the agent responds, you can stream **intermediate progress** to the user. This keeps the UI informed while the agent thinks, searches knowledge, or calls tools.

## Overview

Use the message context's progress methods inside `on_user_chat_message` (or similar handlers). Each call sends an intermediate message to the user before the final reply. The frontend can render these as loading steps, thinking indicators, or tool execution logs.

## Reasoning Messages

Use `send_reasoning_async` to stream the agent's thinking or reasoning steps:

```python
from xians.agents.messaging import UserMessageContext

async def my_chat_handler(context: UserMessageContext) -> None:
    await context.send_reasoning_async("Analyzing the user's question to identify the core requirements...")
    # ... more processing ...
    await context.send_reasoning_async("Breaking down the problem into logical steps.")
    # ...
    await context.reply_async("Here's my analysis...")
```

- **Purpose**: Show internal reasoning or planning steps.
- **Method**: `send_reasoning_async(data, content=None)` — pass a string or object as `data`; use `content` for optional text.
- **Display**: Frontends typically show these as "thinking" or "reasoning" indicators.

## Tool Execution Messages

Use `send_tool_exec_async` to stream tool call steps:

```python
async def my_chat_handler(context: UserMessageContext) -> None:
    await context.send_tool_exec_async("search_knowledge_base(query='best practices')")
    # ... tool runs ...
    await context.send_tool_exec_async("format_response(template='user_friendly')")
    # ...
    await context.reply_async("Here's the result...")
```

- **Purpose**: Show which tools are being invoked (e.g., searches, lookups, formatting).
- **Method**: `send_tool_exec_async(data, content=None)` — pass tool name/args as `data`; use `content` for optional text.
- **Display**: Frontends typically show these as "tool execution" or "calling..." steps.

## Combined Example

```python
async def my_chat_handler(context: UserMessageContext) -> None:
    await context.send_reasoning_async("Analyzing the user's question...")
    await context.send_tool_exec_async("search_knowledge_base(query='...')")
    await context.send_reasoning_async("Synthesizing findings...")
    await context.send_tool_exec_async("format_response(...)")
    await context.reply_async("Here's my answer.")
```

Progress messages are intermediate: they appear while the agent works and before the final `reply_async`. Use them to keep the user informed during longer processing.

## Proactive Progress Messages

You can also send reasoning and tool messages proactively from background workflows via `XiansContext.Messaging`:

```python
from xians.agents.core import XiansContext

await XiansContext.Messaging.send_reasoning_as_supervisor_async(
    text="Analyzing document...",
    participant_id="user-123",
)

await XiansContext.Messaging.send_tool_call_as_supervisor_async(
    text="extract_entities(document_id='doc-456')",
    participant_id="user-123",
)
```

## C# Comparison

| C# | Python |
|----|--------|
| `context.SendReasoningAsync(data, content)` | `await context.send_reasoning_async(data, content)` |
| `context.SendToolExecAsync(data, content)` | `await context.send_tool_exec_async(data, content)` |

## Related

- [Replying to User Messages](./MESSAGING_REPLYING.md) — `reply_async`, `send_data_async`, and other response methods
- [Proactive Messaging](./MESSAGING_PROACTIVE.md) — Send messages without a user context
