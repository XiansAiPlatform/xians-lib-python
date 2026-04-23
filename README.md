# Xians Python SDK

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/XiansAiPlatform/xians-lib-python/actions/workflows/ci.yml/badge.svg)](https://github.com/XiansAiPlatform/xians-lib-python/actions/workflows/ci.yml)
[![Release](https://github.com/XiansAiPlatform/xians-lib-python/actions/workflows/release.yml/badge.svg)](https://github.com/XiansAiPlatform/xians-lib-python/actions/workflows/release.yml)

**Temporal-first agent execution substrate with optional Xians Server integration.**

Build durable, scalable AI agents using ANY framework—LangChain, custom code, or your own implementation. The SDK provides the infrastructure; you provide the intelligence.

---

## ✨ Features

- 🔄 **Durable Execution**: Run agents on Temporal for fault tolerance and reliability
- 🎯 **Framework-Agnostic**: Use ANY agent framework—no vendor lock-in
- 🚀 **Production-Ready**: Typed, tested, and enterprise-grade
- 💬 **Long-Running Sessions**: Support for conversational workflows with state
- 🔌 **Optional Server Integration**: Connect to Xians Server for additional features
- 📊 **Observability**: Built-in logging and Temporal UI integration

---

## 🚀 Quick Start

### Installation

The SDK is distributed directly from GitHub (PyPI release is planned). Pin to
a specific tag in production — don't install from `main` in deployed systems.

**Latest release (recommended):**

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.1.0"
```

**Specific wheel from a GitHub Release:**

```bash
pip install https://github.com/XiansAiPlatform/xians-lib-python/releases/download/v0.1.0/xians_lib_python-0.1.0-py3-none-any.whl
```

**Latest `main` (development only):**

```bash
pip install "git+https://github.com/XiansAiPlatform/xians-lib-python.git@main"
```

**Add to `requirements.txt`:**

```text
xians-lib-python @ git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.1.0
```

**Add to another project's `pyproject.toml`:**

```toml
[project]
dependencies = [
    "xians-lib-python @ git+https://github.com/XiansAiPlatform/xians-lib-python.git@v0.1.0",
]
```

See [docs/RELEASING.md](docs/RELEASING.md) for all installation variants and
the full release process.

### Basic Example

```python
import asyncio

from xians.interfaces.v1.platform import XiansPlatform
from xians.models.v1.configs import XiansOptions
from xians.models.v1.entities import XiansAgentRegistration


async def handle_chat(context):
    text = (context.message.text or "").strip()
    if not text:
        await context.reply_async("Send me a message and I'll echo it back.")
        return

    await context.reply_async(f"Echo: {text}")


async def main():
    # Initialize platform (Temporal config is fetched from Xians Server)
    platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url="https://api.agentri.ai",
            api_key="your-api-key",
        )
    )

    # Register agent
    agent = platform.agents.register(
        XiansAgentRegistration(
            name="MyAgent",
            description="My first agent",
            summary="Echo demo",
            author="you",
            is_template=True,
        )
    )

    # Built-in conversational workflow
    workflow = agent.define_builtin_workflow(name="Supervisor Workflow")
    workflow.on_user_chat_message(handle_chat)

    # Run workers
    await agent.run_all_async()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📖 Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Complete guide for using the SDK
- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - Guide for contributing to the SDK
- **[Releasing Guide](docs/RELEASING.md)** - Versioning, tagging, and publishing releases
- **[Architecture](docs/ARCHITECTURE.md)** - Deep dive into SDK design
- **[API Reference](./docs/API.md)** - Detailed API documentation
- **[Examples](./examples/)** - Working code examples

---

## 🎯 Use Cases

### ✅ One-Shot Agent Execution

Perfect for stateless agent tasks:

```python
from xians.interfaces.v1.agent_client import AgentClient
from xians.models.v1.entities import AgentRequest

client: AgentClient = platform.client()

response = await client.invoke(
    workflow_id="tenant:MyAgent:InvokeWorkflow:demo-1",
    task_queue="xians-default-user-MyAgent-InvokeWorkflow",
    request=AgentRequest(
        agent_key="MyAgent",
        message="Do task",
    ),
)
```

### ✅ Conversational Agents

Long-running sessions with state management:

```python
from xians.interfaces.v1.agent_client import AgentClient
from xians.models.v1.entities import AgentRequest

client: AgentClient = platform.client()

workflow_id = "tenant:MyAgent:Conversation:conv-1"
task_queue = "xians-default-user-MyAgent-Conversation"

handle = await client.start_conversation(
    workflow_id=workflow_id,
    task_queue=task_queue,
    agent_key="MyAgent",
    conversation_id="conv-1",
)

await client.send_signal(
    workflow_id=workflow_id,
    signal_name="user_message",
    AgentRequest(agent_key="MyAgent", message="Hello"),
)
```

### ✅ Multi-Tenant Deployments

Isolated execution per tenant:

```python
for tenant in tenants:
    agent = platform.agents.register(name=f"Agent-{tenant.id}")
    # Automatic task queue isolation per tenant
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│     Your Agent (ANY Framework)              │
│  - LangChain                                │
│  - Custom Code                              │
│  - Or anything else                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│        Xians SDK (This Library)             │
│  - Temporal workflows                       │
│  - Worker management                        │
│  - Optional Xians Server integration        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│            Temporal Server                  │
│  - Durable execution                        │
│  - State management                         │
│  - Retries & fault tolerance                │
└─────────────────────────────────────────────┘
```

**Key Principle**: The SDK owns workflows; you provide activities. This keeps workflows deterministic while allowing complete flexibility in your agent implementation.

---

## 🔑 Key Concepts

### Platform

The main entry point for the SDK:

```python
platform = await XiansPlatform.initialize(options)
```

### Agents

Register agents with unique names:

```python
from xians.models.v1.entities import XiansAgentRegistration

agent = platform.agents.register(
    XiansAgentRegistration(
        name="MyAgent",
        description="My custom agent",
        is_template=True,
    )
)
```

### Workflows

Two patterns provided:

- **Invoke-style workflow**: One-shot request/response via `AgentClient.invoke(...)`
- **Conversational workflow**: Long-running chat via `AgentClient.start_conversation(...)` and signals

### Activities

Where YOUR agent logic lives (black box to SDK):

```python
from temporalio import activity
from xians.models.v1.entities import AgentRequest, AgentResponse

@activity.defn
async def execute_agent_activity(request: AgentRequest) -> AgentResponse:
    # Use ANY framework here
    return AgentResponse(text="...")
```

---

## 🛠️ Development

### Setup

```bash
# Clone repository
git clone https://github.com/XiansAiPlatform/xians-lib-python.git
cd xians-lib-python

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
./scripts/format.sh

# Lint code
./scripts/lint.sh
```

### Running Tests

```bash
pytest                          # Run all tests
pytest --cov=src               # With coverage
pytest tests/test_models.py    # Specific file
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Development Guide](docs/DEVELOPMENT_GUIDE.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run tests and linters
5. Submit a pull request

---

## 📋 Requirements

- Python 3.10 or higher
- Temporal server (local or cloud)
- (Optional) Xians Server access

### Example test agents

Two example agents are provided for testing:

- `examples/custom-workflow-test-agent` (mixed workflows, context inspection):
  ```bash
  cd examples/custom-workflow-test-agent
  pip install -r requirements.txt
  pip install -e ../..
  cp .env.example .env
  python main.py
  ```

- `examples/web-search-agent` (web search with LangChain tools):
  ```bash
  cd examples/web-search-agent
  pip install -r requirements.txt
  pip install -e ../..
  cp .env.example .env
  python main.py
  ```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Links

- **Documentation**: [docs/](./docs/)
- **GitHub**: [XiansAiPlatform/xians-lib-python](https://github.com/XiansAiPlatform/xians-lib-python)
- **Issues**: [GitHub Issues](https://github.com/XiansAiPlatform/xians-lib-python/issues)
- **Releases**: [GitHub Releases](https://github.com/XiansAiPlatform/xians-lib-python/releases)
- **Temporal**: [temporal.io](https://temporal.io)
- **Xians Platform**: [xians.ai](https://xians.ai)

---

## 💬 Support

- 📧 Email: 

---

**Built with ❤️ by the Xians Platform team**

