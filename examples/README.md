# Xians Platform Examples

Complete examples demonstrating different agent patterns with Xians Platform.

## Examples Overview

| Example | Type | Use Case | Complexity |
|---------|------|----------|------------|
| `basic_invoke_agent.py` | Invoke | One-shot tasks | ⭐ Beginner |
| `conversational_agent.py` | Conversational | Multi-turn chats | ⭐⭐ Intermediate |

## Quick Start

### 1. Install Dependencies

```bash
cd /path/to/xians-lib-python
pip install -e .
```

### 2. Choose Your Pattern

**Need a simple task executor?** → Use **Invoke Agent**
- Single request/response
- Stateless execution
- Quick tasks (seconds)

**Need a chatbot/assistant?** → Use **Conversational Agent**
- Multi-turn conversations
- Maintains context
- Long-running (minutes to hours)

## Invoke Agent Example

### What It Does
Executes a single task and returns a result. Like calling a function.

### Run It

**Terminal 1 - Start Worker:**
```bash
python examples/basic_invoke_agent.py
```

**Terminal 2 - Invoke Agent:**
```bash
python examples/invoke_agent_client.py
```

### Expected Output

Worker:
```
Started worker on task queue: xians-default-user-EchoAgent-InvokeEcho
Running 1 workers. Press Ctrl+C to stop.
```

Client:
```
✅ SUCCESS! Agent Response:
   📝 Text: Echo: Hello from the client!
```

### Files
- `basic_invoke_agent.py` - Worker that runs the agent
- `invoke_agent_client.py` - Client that invokes the agent

### Learn More
See: [HOW_TO_INVOKE.md](../HOW_TO_INVOKE.md) (if created in PythonTest directory)

---

## Conversational Agent Example

### What It Does
Maintains a long-running conversation with context awareness. Like a chatbot.

### Run It

**Terminal 1 - Start Worker:**
```bash
python examples/conversational_agent.py
```

**Terminal 2 - Start Conversation:**
```bash
# Interactive mode
python examples/conversational_agent_client.py

# Or demo mode
python examples/conversational_agent_client.py --demo
```

### Expected Output

Worker:
```
Conversational agent registered and ready
Task queue: xians-default-user-ChatBot-ChatConversation
Waiting for conversations to start...
```

Client (Interactive):
```
💬 Chat started! Type your messages below.

You: Hello!
Agent: [Processing...]

You: What did I say earlier?
Agent: [Processing...]
```

### Files
- `conversational_agent.py` - Worker that runs the chatbot
- `conversational_agent_client.py` - Client for chatting with the bot

### Learn More
See: [CONVERSATIONAL_GUIDE.md](./CONVERSATIONAL_GUIDE.md)

---

## Comparison: Invoke vs Conversational

### Invoke Agent
```python
# One call, one response
response = await client.invoke(
    workflow_id="task-123",
    task_queue="...",
    request=AgentRequest(message="Do task"),
)
print(response.text)
```

**Characteristics:**
- ✅ Simple to use
- ✅ Stateless
- ✅ Fast execution
- ❌ No memory between calls
- ❌ Single request/response only

**Best For:**
- Data transformations
- Quick calculations
- API calls
- One-off tasks
- Webhooks handlers

### Conversational Agent
```python
# Start conversation
handle = await client.start_conversation(
    workflow_id="chat-123",
    task_queue="...",
    agent_key="ChatBot",
    conversation_id="conv-456",
)

# Send multiple messages
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

# End conversation
await client.cancel_workflow("chat-123")
```

**Characteristics:**
- ✅ Maintains context
- ✅ Multi-turn interactions
- ✅ Stateful
- ❌ More complex setup
- ❌ Requires lifecycle management

**Best For:**
- Chatbots
- Customer support agents
- Interview bots
- Guided workflows
- Assistants

---

## Architecture

### Invoke Pattern
```
Client          Temporal          Worker
  |                |                |
  |--[Request]---->|                |
  |                |--[Dispatch]--->|
  |                |          [Execute]
  |                |<--[Result]-----|
  |<--[Response]---|                |
  |                |                |
```

### Conversational Pattern
```
Client          Temporal          Worker
  |                |                |
  |--[Start]------>|                |
  |                |--[Dispatch]--->|
  |                |          [Initialize]
  |                |                |
  |--[Message 1]-->|--[Signal]----->|
  |                |          [Process]
  |                |                |
  |--[Message 2]-->|--[Signal]----->|
  |                |          [Process]
  |                |                |
  |--[Cancel]----->|--[Terminate]-->|
  |                |          [Cleanup]
```

---

## Configuration

All examples use the same configuration structure:

```python
platform = await XiansPlatform.initialize(
    XiansOptions(
        server_url="https://api.agentri.ai",
        api_key="YOUR_API_KEY",
        temporal=None,  # Auto-fetched from Xians Server
        llm=LLMConfig(
            provider="google_vertex",
            model="gemini-2.5-flash",
            api_key="YOUR_LLM_API_KEY",
        ),
    )
)
```

### Environment Variables

You can also use environment variables:

```bash
export XIANS_SERVER_URL="https://api.agentri.ai"
export XIANS_API_KEY="your-api-key"
export LLM_API_KEY="your-llm-key"
```

---

## Customization

### Add Your Own Agent

1. **Create activity function:**
```python
@activity.defn
async def my_custom_activity(request: AgentRequest) -> AgentResponse:
    # Your logic here
    result = await do_something(request.message)
    return AgentResponse(text=result)
```

2. **Register agent:**
```python
agent = platform.agents.register(
    name="MyAgent",
    description="My custom agent",
    system_scoped=False,
)
```

3. **Define workflow:**
```python
# For invoke pattern
agent.define_invoke_workflow(
    name="MyWorkflow",
    workers=2,
    activity_func=my_custom_activity,
)

# For conversational pattern
agent.define_conversation_workflow(
    name="MyConversation",
    workers=2,
    activity_func=my_custom_activity,
)
```

4. **Run it:**
```python
await platform.run_all()
```

### Add LLM Integration

```python
from openai import AsyncOpenAI

llm_client = AsyncOpenAI(api_key="your-key")

@activity.defn
async def llm_powered_activity(request: AgentRequest) -> AgentResponse:
    response = await llm_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": str(request.message)},
        ],
    )
    
    return AgentResponse(
        text=response.choices[0].message.content,
        usage={
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        },
    )
```

---

## Troubleshooting

### Worker Not Starting

**Error**: `Failed to connect to Temporal`

**Solution**:
1. Check your internet connection
2. Verify API key is valid
3. Check Xians Server is accessible:
   ```bash
   curl https://api.agentri.ai/health
   ```

### Client Can't Find Worker

**Error**: `No workers available`

**Solution**:
1. Ensure worker is running in another terminal
2. Check task queue names match exactly
3. Verify both use the same namespace

### Activity Errors

**Error**: Activity fails with exception

**Solution**:
1. Check worker logs for detailed error
2. Add try/except in activity:
   ```python
   @activity.defn
   async def safe_activity(request: AgentRequest) -> AgentResponse:
       try:
           result = await process(request)
           return AgentResponse(text=result)
       except Exception as e:
           logger.error(f"Activity error: {e}")
           return AgentResponse(
               text=f"Error: {str(e)}",
               metadata={"error": True}
           )
   ```

---

## Production Checklist

Before deploying to production:

- [ ] Replace demo API keys with production keys
- [ ] Add proper error handling
- [ ] Implement logging and monitoring
- [ ] Add rate limiting
- [ ] Use persistent storage (Redis/DB) for state
- [ ] Set appropriate timeouts
- [ ] Add health checks
- [ ] Configure auto-scaling
- [ ] Implement authentication/authorization
- [ ] Add tests
- [ ] Document your agent's behavior
- [ ] Set up CI/CD

---

## Next Steps

1. **Try the examples** - Run both patterns to understand the differences
2. **Read the guides** - Check out the detailed guides for each pattern
3. **Customize** - Modify the examples for your use case
4. **Add LLM** - Integrate with OpenAI, Anthropic, or Google AI
5. **Deploy** - Move to production with proper monitoring

## Resources

- [Xians Platform Documentation](../docs/)
- [Temporal Python SDK](https://docs.temporal.io/dev-guide/python)
- [API Reference](../docs/API.md) (if exists)

## Getting Help

- **Issues**: Open an issue on GitHub
- **Questions**: Check the documentation
- **Community**: Join our Discord (if available)

---

Happy building with Xians Platform! 🚀

