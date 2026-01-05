# Xians Python SDK

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](../LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)

Enterprise-grade Python SDK for building Temporal-native AI agents with Xians platform integration.

## Features

- 🔄 **Temporal-Native Agent Runtime**: Build long-running, durable agent workflows on Temporal
- 🔌 **Xians Server Integration**: Seamless integration with Xians platform for knowledge, documents, and conversations
- 🤖 **LLM Framework-Agnostic**: Bring your own LLM provider (OpenAI, Anthropic, Azure, etc.)
- 🛡️ **Enterprise-Grade**: Type-safe, tested, and production-ready
- 📦 **Flexible Workflows**: Support for both built-in and custom workflow patterns

## Installation

```bash
pip install xians-lib-python
```

For development:

```bash
pip install "xians-lib-python[dev]"
```

## Quick Start

### Platform-Style Usage

```python
from xians.platform.v1 import XiansPlatform, XiansOptions

# Initialize the platform
platform = await XiansPlatform.initialize(
    XiansOptions(
        server_url="https://api.xians.ai",
        api_key="your-api-key",
        temporal=None,  # Auto-fetch from server
        llm=LLMOptions(provider="openai", model="gpt-4")
    )
)

# Register an agent
agent = platform.agents.register(name="My Agent", system_scoped=False)

# Define a built-in workflow
wf = agent.workflows.define_builtin("Conversational", workers=2)

# Handle chat messages
@wf.on_user_chat_message
async def handle_chat(ctx):
    resp = await ctx.llm.chat(
        messages=[{"role": "user", "content": ctx.message.text}],
        model=ctx.config.llm.model,
    )
    await ctx.reply(resp.text)

# Run all workflows
await agent.run_all()
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/xians-platform/xians-lib-python.git
cd xians-lib-python

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Quick smoke test (30 seconds)
python smoke_test.py

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test types
pytest -m unit
pytest -m integration
```

### Verify Installation

```bash
# Quick import check
python -c "
from src.models.v1 import LLMMessage, AgentDefinition
from src.constants.v1 import LLMProvider
from src.utils.v1 import compute_hash
print('✅ Library is working!')
"

# Or run the smoke test
python smoke_test.py
```

For detailed verification instructions, see [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md).

### Code Quality

```bash
# Format code
black src tests
isort src tests

# Lint
ruff check src tests

# Type check
mypy src
```

## Project Structure

```
src/
├── configs/v1/          # Configuration models and settings
├── constants/v1/        # Constants and enums
├── exceptions/v1/       # Custom exception classes
├── interfaces/v1/       # Abstract base classes and protocols
├── llm_adapters/v1/     # LLM provider adapters
├── models/v1/           # Pydantic data models
├── temporal_workflows/v1/ # Temporal workflow definitions
└── utils/v1/            # Utility functions and helpers
```

## Documentation

- [Full Documentation](https://docs.xians.ai/python)
- [API Reference](https://docs.xians.ai/python/api)
- [Examples](https://github.com/xians-platform/xians-examples-python)

## Requirements

- Python 3.10 or higher
- Temporal server (local or cloud)
- Xians platform account (optional, for platform features)

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](DEVELOPMENT_GUIDE.md) before submitting PRs.

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Support

- 📧 Email: support@xians.ai
- 💬 Discord: [Join our community](https://discord.gg/xians)
- 🐛 Issues: [GitHub Issues](https://github.com/xians-platform/xians-lib-python/issues)

## Roadmap

- [x] Core SDK structure
- [ ] Temporal workflow runtime
- [ ] Xians server client
- [ ] LLM adapters (OpenAI, Anthropic, Azure)
- [ ] Built-in workflow types
- [ ] Knowledge & document APIs
- [ ] Usage tracking
- [ ] Comprehensive examples

