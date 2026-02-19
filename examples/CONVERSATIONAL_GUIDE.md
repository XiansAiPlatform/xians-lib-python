# Conversational Agent Guide

A comprehensive guide to building and using conversational agents with Xians Platform.

## Overview

**Conversational agents** are different from simple invoke agents:

| Feature | Invoke Agent | Conversational Agent |
|---------|--------------|---------------------|
| **Workflow Duration** | Short-lived (seconds) | Long-running (minutes to hours) |
| **State** | Stateless | Stateful across messages |
| **Communication** | Request → Response | Bidirectional signals |
| **Use Case** | Single task execution | Multi-turn conversations |
| **History** | No memory | Maintains context |

## Quick Start

### Step 1: Start the Worker

In one terminal, start the conversational agent worker:

```bash
cd "/Users/poornimaka/Library/CloudStorage/OneDrive-99x/Xians Platform/pythonLib/xians-lib-python"
python examples/conversational_agent.py
```

Expected output:
```
Starting Conversational Agent...
Conversational agent registered and ready
Task queue: xians-default-user-ChatBot-ChatConversation
Waiting for conversations to start...
```

### Step 2: Run the Client

In a **new terminal**, run the client:

```bash
# Interactive mode
python examples/conversational_agent_client.py

# Or demo mode with predefined messages
python examples/conversational_agent_client.py --demo
```

### Step 3: Chat!

In interactive mode, you'll see:
```
💬 Conversational Agent Client
================================================
📋 Conversation Details:
   Workflow ID: chat-abc123
   Conversation ID: def456...

💬 Chat started! Type your messages below.
================================================

You: 
```

Type your messages and see the agent respond!

## How It Works

### 1. Workflow Lifecycle

```
Client              Temporal           Worker
  |                    |                 |
  |--Start Conv------->|                 |
  |                    |<--Poll----------|
  |                    |--Assign-------->|
  |                    |            [Initialize]
  |                    |                 |
  |--Signal(msg1)----->|--Deliver------->|
  |                    |            [Process]
  |                    |<--Continue------|
  |                    |                 |
  |--Signal(msg2)----->|--Deliver------->|
  |                    |            [Process]
  |                    |<--Continue------|
  |                    |                 |
  |--Cancel----------->|--Terminate----->|
  |                    |            [Cleanup]
```

### 2. Key Differences from Invoke

**Invoke Agent (One-shot)**:
```python
# Start and wait for result in one call
response = await client.invoke(
    workflow_id="task-123",
    task_queue="...",
    request=AgentRequest(message="Do something"),
)
print(response.text)  # Done!
```

**Conversational Agent (Long-running)**:
```python
# 1. Start the conversation workflow
handle = await client.start_conversation(
    workflow_id="chat-123",
    task_queue="...",
    agent_key="ChatBot",
    conversation_id="conv-456",
)

# 2. Send multiple messages over time
await client.send_signal(
    workflow_id="chat-123",
    signal_name="user_message",
    AgentRequest(message="Hello"),
)

await client.send_signal(
    workflow_id="chat-123",
    signal_name="user_message",
    AgentRequest(message="How are you?"),
)

# 3. Cancel when done
await client.cancel_workflow("chat-123")
```

### 3. State Management

The conversational agent maintains state across messages:

```python
# In the activity
conversation_history: dict[str, list[dict]] = {}

@activity.defn
async def execute_conversational_activity(request: AgentRequest) -> AgentResponse:
    conv_id = request.conversation_id
    
    # Get existing history
    history = conversation_history.get(conv_id, [])
    
    # Add new message
    history.append({"role": "user", "content": request.message})
    
    # Generate response with context
    response = generate_response_with_history(history)
    
    # Save response
    history.append({"role": "assistant", "content": response})
    conversation_history[conv_id] = history
    
    return AgentResponse(text=response)
```

## Customization

### Add Real LLM Integration

Replace the mock response generator with actual LLM calls:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def generate_contextual_response(
    message: str, 
    history: list[dict[str, str]]
) -> str:
    """Use OpenAI for real conversations."""
    # Convert history to OpenAI format
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    messages.extend(history)
    
    # Call OpenAI
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=messages,
    )
    
    return response.choices[0].message.content
```

### Add Persistent Storage

Use Redis or a database instead of in-memory storage:

```python
import redis.asyncio as redis

redis_client = redis.from_url("redis://localhost")

@activity.defn
async def execute_conversational_activity(request: AgentRequest) -> AgentResponse:
    conv_id = request.conversation_id
    
    # Load history from Redis
    history_json = await redis_client.get(f"conv:{conv_id}")
    history = json.loads(history_json) if history_json else []
    
    # Process message
    history.append({"role": "user", "content": request.message})
    response_text = await generate_response(history)
    history.append({"role": "assistant", "content": response_text})
    
    # Save to Redis
    await redis_client.set(
        f"conv:{conv_id}",
        json.dumps(history),
        ex=3600  # 1 hour expiry
    )
    
    return AgentResponse(text=response_text)
```

### Add RAG/Knowledge Base

Integrate with a knowledge base for grounded responses:

```python
from chromadb import AsyncClient

chroma = AsyncClient()
collection = chroma.get_collection("knowledge_base")

async def generate_contextual_response(
    message: str,
    history: list[dict[str, str]]
) -> str:
    # Search knowledge base
    results = await collection.query(
        query_texts=[message],
        n_results=3,
    )
    
    context = "\n".join(results["documents"][0])
    
    # Build prompt with context
    messages = [
        {
            "role": "system",
            "content": f"Use this context to answer:\n{context}"
        }
    ]
    messages.extend(history)
    
    # Generate response with context
    return await call_llm(messages)
```

### Add Tool Calling

Enable the agent to perform actions:

```python
def get_weather(location: str) -> str:
    """Get weather for a location."""
    # Call weather API
    return f"Weather in {location}: Sunny, 72°F"

def calculate(expression: str) -> str:
    """Calculate a math expression."""
    return str(eval(expression))

TOOLS = {
    "get_weather": get_weather,
    "calculate": calculate,
}

async def generate_contextual_response(
    message: str,
    history: list[dict[str, str]]
) -> str:
    # Check for tool invocations
    if message.startswith("/weather"):
        location = message.split(None, 1)[1]
        return TOOLS["get_weather"](location)
    
    if message.startswith("/calc"):
        expr = message.split(None, 1)[1]
        return TOOLS["calculate"](expr)
    
    # Normal conversation
    return await call_llm(history)
```

## Advanced Features

### Query Conversation State

Add queries to check conversation state:

```python
# In workflow definition (you need to implement this in workflows.py)
@workflow.query
def get_message_count(self) -> int:
    return len(self.message_history)

@workflow.query
def get_last_message(self) -> str | None:
    return self.message_history[-1] if self.message_history else None

# In client
message_count = await client.query(
    workflow_id="chat-123",
    query_name="get_message_count",
)
print(f"Messages exchanged: {message_count}")
```

### Handle Disconnections

Reconnect to existing conversations:

```python
async def reconnect_to_conversation(workflow_id: str):
    """Reconnect to an existing conversation."""
    try:
        # Get existing workflow handle
        handle = client.client.get_workflow_handle(workflow_id)
        
        # Check if still running
        description = await handle.describe()
        if description.status == "Running":
            print("✅ Reconnected to existing conversation")
            return handle
        else:
            print("⚠️  Conversation has ended")
            return None
            
    except Exception as e:
        print(f"❌ Could not reconnect: {e}")
        return None
```

### Implement Typing Indicators

Show when the agent is processing:

```python
# Send a signal when starting to process
await client.send_signal(
    workflow_id="chat-123",
    signal_name="typing_start",
)

# Process message
await asyncio.sleep(2)  # Simulate thinking

# Send response
await client.send_signal(
    workflow_id="chat-123",
    signal_name="user_message",
    request,
)
```

### Add Message Streaming

Stream responses token by token:

```python
async def stream_response(message: str, history: list):
    """Stream response tokens as they're generated."""
    async for token in llm.stream_chat(history):
        yield token

# In activity
async def execute_conversational_activity(request: AgentRequest):
    # Stream to external queue/websocket
    async for token in stream_response(request.message, history):
        await send_to_websocket(request.conversation_id, token)
    
    return AgentResponse(text="[Streaming complete]")
```

## Production Considerations

### 1. Conversation Timeout

Set appropriate timeouts:

```python
# In workflow
@workflow.defn
class ConversationWorkflow:
    async def run(self, agent_key: str, conversation_id: str):
        # Timeout after 1 hour of inactivity
        timeout = timedelta(hours=1)
        # Implementation depends on your workflow structure
```

### 2. Rate Limiting

Prevent abuse:

```python
from datetime import datetime, timedelta

rate_limits: dict[str, list[datetime]] = {}

async def check_rate_limit(conv_id: str) -> bool:
    """Allow max 10 messages per minute."""
    now = datetime.now()
    cutoff = now - timedelta(minutes=1)
    
    # Get recent messages
    recent = [
        ts for ts in rate_limits.get(conv_id, [])
        if ts > cutoff
    ]
    
    if len(recent) >= 10:
        return False
    
    recent.append(now)
    rate_limits[conv_id] = recent
    return True
```

### 3. Graceful Shutdown

Handle cleanup properly:

```python
async def shutdown_conversation(workflow_id: str):
    """Gracefully end a conversation."""
    try:
        # Save final state
        await save_conversation_history(workflow_id)
        
        # Send farewell message
        await client.send_signal(
            workflow_id=workflow_id,
            signal_name="user_message",
            AgentRequest(message="[System: Conversation ending]"),
        )
        
        await asyncio.sleep(1)
        
        # Cancel workflow
        await client.cancel_workflow(workflow_id)
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
```

### 4. Monitoring

Track conversation metrics:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ConversationMetrics:
    conversation_id: str
    started_at: datetime
    message_count: int
    avg_response_time: float
    user_satisfaction: float | None

async def track_metrics(conv_id: str):
    """Track and report metrics."""
    metrics = ConversationMetrics(
        conversation_id=conv_id,
        started_at=datetime.now(),
        message_count=0,
        avg_response_time=0.0,
        user_satisfaction=None,
    )
    
    # Send to monitoring system
    await send_to_datadog(metrics)
```

## Troubleshooting

### Workflow Not Receiving Signals

**Problem**: Messages sent via signals don't reach the workflow.

**Solutions**:
1. Verify workflow is still running:
   ```python
   handle = client.client.get_workflow_handle(workflow_id)
   desc = await handle.describe()
   print(desc.status)  # Should be "Running"
   ```

2. Check signal name matches workflow definition

3. Ensure workflow hasn't timed out

### State Not Persisting

**Problem**: Conversation forgets previous messages.

**Solutions**:
1. Use persistent storage (Redis, DB) instead of in-memory
2. Check conversation_id is consistent across messages
3. Verify activity is actually saving state

### High Latency

**Problem**: Responses take too long.

**Solutions**:
1. Use async LLM calls
2. Implement caching for common queries
3. Optimize knowledge base searches
4. Consider response streaming

## Next Steps

1. **Integrate Real LLM**: Replace mock responses with OpenAI, Anthropic, or Google AI
2. **Add Knowledge Base**: Implement RAG with ChromaDB, Pinecone, or Weaviate
3. **Build UI**: Create a web interface with React/Vue + WebSockets
4. **Add Analytics**: Track conversation quality and user satisfaction
5. **Implement Multi-turn Planning**: Add agent planning and reasoning capabilities

## Resources

- [Temporal Workflows Documentation](https://docs.temporal.io/workflows)
- [Signals and Queries Guide](https://docs.temporal.io/dev-guide/python/features#signals)
- [OpenAI Chat API](https://platform.openai.com/docs/guides/chat)
- [Xians Platform Documentation](../../docs/)

Happy building! 🚀

