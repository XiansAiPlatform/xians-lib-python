# Xians Python SDK

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/xians-platform/xians-lib-python/workflows/tests/badge.svg)](https://github.com/xians-platform/xians-lib-python/actions)

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

```bash
pip install xians-lib-python
```

### Basic Example

```python
import asyncio
from temporalio import activity
from xians.platform.v1 import XiansPlatform, XiansOptions, AgentRequest, AgentResponse

# Define your agent activity (ANY framework allowed!)
@activity.defn
async def execute_agent_activity(request: AgentRequest) -> AgentResponse:
    # Your agent logic here - completely framework-agnostic
    result = your_agent_framework.run(request.message)
    return AgentResponse(text=result)

async def main():
    # Initialize platform
    platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url="https://api.xians.ai",
            api_key="your-api-key",
            temporal=TemporalConfig(host="localhost", port=7233),
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="sk-..."),
        )
    )

    # Register agent
    agent = platform.agents.register(name="MyAgent")
    agent.define_invoke_workflow(activity_func=execute_agent_activity)

    # Run workers
    await platform.run_all()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📖 Documentation

- **[User Guide](USER_GUIDE.md)** - Complete guide for using the SDK
- **[Development Guide](DEVELOPMENT_GUIDE.md)** - Guide for contributing to the SDK
- **[Architecture](ARCHITECTURE.md)** - Deep dive into SDK design
- **[API Reference](./docs/API.md)** - Detailed API documentation
- **[Examples](./examples/)** - Working code examples

---

## 🎯 Use Cases

### ✅ One-Shot Agent Execution

Perfect for stateless agent tasks:

```python
agent.define_invoke_workflow(
    name="InvokeAgent",
    workers=2,
    activity_func=execute_agent_activity,
)
```

### ✅ Conversational Agents

Long-running sessions with state management:

```python
agent.define_conversation_workflow(
    name="Conversation",
    workers=1,
    activity_func=execute_conversational_agent,
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
agent = platform.agents.register(name="MyAgent", system_scoped=False)
```

### Workflows

Two types provided:

- **InvokeAgentWorkflow**: One-shot request-response
- **ConversationWorkflow**: Long-running with state

### Activities

Where YOUR agent logic lives (black box to SDK):

```python
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
git clone https://github.com/xians-platform/xians-lib-python.git
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

We welcome contributions! Please see our [Development Guide](DEVELOPMENT_GUIDE.md) for details.

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

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

---

## 🔗 Links

- **Documentation**: [docs/](./docs/)
- **GitHub**: [xians-platform/xians-lib-python](https://github.com/xians-platform/xians-lib-python)
- **Issues**: [GitHub Issues](https://github.com/xians-platform/xians-lib-python/issues)
- **Temporal**: [temporal.io](https://temporal.io)
- **Xians Platform**: [xians.ai](https://xians.ai)

---

## 💬 Support

- 📧 Email: 

---

**Built with ❤️ by the Xians Platform team**

