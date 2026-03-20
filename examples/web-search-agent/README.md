# Web Search Agent

A Python web search agent built with **LangChain + DuckDuckGo**, registered on the **Xians platform** using the same pattern as the C# example agents (secrets-agent, healthcare-agent).

DuckDuckGo search is **free** and requires **no API key**.

## Architecture

```
Xians Platform
  └── Web Search Agent (registered)
        └── Supervisor Workflow (BuiltinWorkflow)
              └── on_user_chat_message(handler)
                    └── WebSearchSubAgent.run_async(context)
                          └── LangGraph ReAct Agent
                                ├── DuckDuckGo Web Search tool
                                └── Current DateTime tool
```

## Setup

1. **Install dependencies:**

```bash
cd examples/web-search-agent
pip install -r requirements.txt
pip install -e ../..  # Install xians-lib-python
```

2. **Configure environment:**

```bash
cp .env.example .env
# Edit .env with your keys
```

3. **Run the agent:**

```bash
python main.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XIANS_SERVER_URL` | Xians platform server URL |
| `XIANS_API_KEY` | Base64-encoded X.509 certificate |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o-mini |

> DuckDuckGo search requires **no API key** — it works out of the box.

## How It Works

This example mirrors the C# agent pattern exactly:

**C# (secrets-agent/Program.cs):**
```csharp
var xiansPlatform = await XiansPlatform.InitializeAsync(new XiansOptions { ... });
var xiansAgent = xiansPlatform.Agents.Register(new XiansAgentRegistration { ... });
var workflow = xiansAgent.Workflows.DefineBuiltIn(name: "Supervisor Workflow");
workflow.OnUserChatMessage(async (context) => {
    var response = await subAgent.RunAsync(context);
    await context.ReplyAsync(response);
});
await xiansAgent.RunAllAsync();
```

**Python (this example):**
```python
xians_platform = await XiansPlatform.initialize(XiansOptions(...))
xians_agent = xians_platform.agents.register(XiansAgentRegistration(...))
workflow = xians_agent.define_builtin_workflow(name="Supervisor Workflow")
workflow.on_user_chat_message(handle_chat)  # calls sub_agent.run_async(ctx)
await xians_agent.run_all_async()
```

## Tools

The agent has access to:

- **DuckDuckGo Web Search** — Free real-time web search with snippets and links
- **Current DateTime** — Returns the current UTC date/time

## Metrics

LLM token usage (prompt, completion, total) is automatically reported to the Xians metrics API after each agent response. This uses `context.metrics` with token counts extracted from the LangChain/LangGraph response metadata.
