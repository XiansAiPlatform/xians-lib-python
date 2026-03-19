# Custom Workflow Test Agent

An example agent that demonstrates **three** workflow types:

- A **Built-in conversational workflow** (`Supervisor Workflow`) using `BuiltinWorkflow` + `on_user_chat_message(...)`
- A **Custom Temporal workflow** that takes **start parameters** (so the Xians UI shows **Input Parameters**)
- A **Context Inspector workflow** that validates `XiansContext.CurrentAgent` / `CurrentWorkflow` resolve correctly inside a Temporal activity

This is useful for validating that the Python SDK matches C# behavior around:

- Built-in workflows uploading `parameterDefinitions: []` (no forced `input`)
- Custom workflows uploading `parameterDefinitions` derived from the workflow `run(...)` signature (and/or explicitly set)
- `XiansContext.CurrentAgent` / `CurrentWorkflow` resolving from Temporal activity context

## Workflows

### 1) Built-in: `Supervisor Workflow`
- Type: `{AgentName}:Supervisor Workflow`
- Message type: chat (via `HandleInboundChatOrData` signal)
- UI: chat-style interaction (no start parameters)
- Also prints `[Agent: ... | Workflow: ...]` in the echo response to demonstrate live `CurrentAgent` / `CurrentWorkflow` access

### 2) Custom: `Custom Input Workflow`
- Type: `{AgentName}:Custom Input Workflow`
- Trigger: **Start workflow** with parameters (rendered by UI from `parameterDefinitions`)
- Parameters: `input` (string), `times` (int, optional), `uppercase` (bool, optional)
- Returns: a simple string result

### 3) Custom: `Context Inspector Workflow`
- Type: `{AgentName}:Context Inspector Workflow`
- Trigger: **Start workflow** with a `query` string parameter
- Returns: a JSON report containing:
  - Current async context (`tenant_id`, `participant_id`, `workflow_id`, etc.)
  - `CurrentAgent` details (name, system_scoped, tenant, workflow count)
  - `CurrentWorkflow` details (type, name, workers, system_scoped, tenant)
  - List of all registered agents and workflows
- This proves the Python SDK's `XiansContext.CurrentAgent` / `CurrentWorkflow` properties work inside Temporal activities, matching C# behavior

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

## Local Knowledge Uploads

This example now follows the same startup pattern used in `web-search-agent`:
- Define a `knowledge_files` list in `main.py`
- Call `await agent.knowledge.upload_from_file(...)` for each local file

Files uploaded from `knowledge/`:
- `system-instructions.md` -> `markdown`
- `agent-profile.json` -> `json`
- `sample-notes.txt` -> `text`
- `workflow-config.xml` -> `xml`
- `settings.yaml` -> `yaml`
- `settings-alt.yml` -> `yaml`

Run the agent from this directory so relative knowledge paths resolve correctly:

```bash
cd examples/custom-workflow-test-agent
python main.py
```
