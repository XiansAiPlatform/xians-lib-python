# Custom Workflow Test Agent

An example agent that demonstrates **both**:

- A **Built-in conversational workflow** (`Supervisor Workflow`) using `BuiltinWorkflow` + `on_user_chat_message(...)`
- A **Custom Temporal workflow** that takes **start parameters** (so the Xians UI shows **Input Parameters**)

This is useful for validating that the Python SDK matches C# behavior around:

- Built-in workflows uploading `parameterDefinitions: []` (no forced `input`)
- Custom workflows uploading `parameterDefinitions` derived from the workflow `run(...)` signature (and/or explicitly set)

## Workflows

### 1) Built-in: `Supervisor Workflow`
- Type: `{AgentName}:Supervisor Workflow`
- Message type: chat (via `HandleInboundChatOrData` signal)
- UI: chat-style interaction (no start parameters)

### 2) Custom: `Custom Input Workflow`
- Type: `{AgentName}:Custom Input Workflow`
- Trigger: **Start workflow** with parameters (rendered by UI from `parameterDefinitions`)
- Returns: a simple string result

## Setup

```bash
cd examples/custom-workflow-test-agent
pip install -r requirements.txt
pip install -e ../..
cp .env.example .env
python main.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XIANS_SERVER_URL` | Xians platform server URL |
| `XIANS_API_KEY` | Base64-encoded X.509 certificate |

