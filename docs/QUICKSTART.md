# Xians Python SDK - Quick Start Guide

## Installation

### For Users

```bash
pip install xians-lib-python
```

### For Developers

```bash
# Clone the repository
git clone https://github.com/xians-platform/xians-lib-python.git
cd xians-lib-python

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Development Workflow

### Run Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_models.py

# Run tests matching a pattern
pytest -k "test_llm"

# Run with coverage
pytest --cov=src --cov-report=html
# View coverage report: open htmlcov/index.html
```

### Code Formatting

```bash
# Check formatting (will show what would change)
black --check src tests

# Apply formatting
black src tests

# Sort imports
isort src tests

# Or use the script
./scripts/format.sh
```

### Linting

```bash
# Run ruff
ruff check src tests

# Auto-fix issues
ruff check --fix src tests

# Run mypy type checking
mypy src

# Or use the script
./scripts/lint.sh
```

### Full CI Check

```bash
# Run all checks (format + lint + test)
./scripts/ci.sh
```

## Project Structure

```
xians-lib-python/
├── src/                    # Source code
│   ├── configs/           # Configuration management
│   ├── constants/v1/      # Constants and enums
│   ├── exceptions/v1/     # Custom exceptions
│   ├── interfaces/v1/     # Abstract interfaces
│   ├── llm_adapters/v1/   # LLM provider adapters
│   ├── models/v1/         # Pydantic data models
│   ├── temporal_workflows/v1/ # Temporal workflows
│   └── utils/v1/          # Utility functions
├── tests/                 # Test suite
│   ├── conftest.py       # Pytest fixtures
│   ├── test_constants.py
│   ├── test_exceptions.py
│   ├── test_models.py
│   └── test_utils.py
├── scripts/              # Development scripts
│   ├── format.sh        # Format code
│   ├── lint.sh          # Run linters
│   ├── test.sh          # Run tests
│   └── ci.sh            # Full CI check
├── docs/                # Documentation
├── pyproject.toml       # Project configuration
├── README.md            # Main documentation
└── CONTRIBUTING.md      # Contribution guidelines
```

## Key Modules

### Models (`src/models/v1/`)

Pydantic models for data validation:

```python
from src.models.v1 import XiansOptions, LLMConfig
from src.constants.v1 import LLMProvider
from pydantic import SecretStr

# Create configuration
options = XiansOptions(
    server_url="https://api.xians.ai",
    api_key=SecretStr("your-key"),
    llm=LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
    )
)
```

### Exceptions (`src/exceptions/v1/`)

Custom exception hierarchy:

```python
from src.exceptions.v1 import XiansError, LLMError

try:
    # Your code
    pass
except LLMError as e:
    print(f"LLM error: {e.message}")
    print(f"Provider: {e.provider}")
    print(f"Details: {e.details}")
```

### Constants (`src/constants/v1/`)

Enums and constants:

```python
from src.constants.v1 import LLMProvider, WorkflowType, MessageRole

provider = LLMProvider.OPENAI
workflow = WorkflowType.CONVERSATIONAL
role = MessageRole.USER
```

## Testing Guidelines

### Writing Tests

1. Place test files in `tests/` directory
2. Name test files `test_*.py`
3. Name test functions `test_*`
4. Use fixtures from `conftest.py`
5. Mark tests appropriately:
   - `@pytest.mark.unit` for unit tests
   - `@pytest.mark.integration` for integration tests
   - `@pytest.mark.slow` for slow-running tests

Example:

```python
import pytest
from src.models.v1 import LLMConfig
from src.constants.v1 import LLMProvider

@pytest.mark.unit
def test_llm_config_creation():
    """Test LLMConfig creation with required fields."""
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
    )
    assert config.provider == LLMProvider.OPENAI
    assert config.model == "gpt-4"
```

### Using Fixtures

```python
def test_with_sample_config(sample_llm_config):
    """Use fixture from conftest.py."""
    assert sample_llm_config.provider == LLMProvider.OPENAI
```

## Code Style Guidelines

### Type Hints

Always use type hints:

```python
from typing import Any

def process_data(data: dict[str, Any], count: int) -> list[str]:
    """Process data and return results."""
    results: list[str] = []
    # Implementation
    return results
```

### Docstrings

Use Google-style docstrings:

```python
def compute_hash(content: str) -> str:
    """
    Compute SHA-256 hash of content.

    Args:
        content: Content to hash

    Returns:
        Hexadecimal hash string

    Raises:
        ValueError: If content is empty
    """
    pass
```

### Error Handling

Never swallow exceptions:

```python
# ❌ Bad
try:
    risky_operation()
except Exception:
    pass

# ✅ Good
from src.exceptions.v1 import XiansError

try:
    risky_operation()
except SomeSpecificError as e:
    raise XiansError("Operation failed", cause=e) from e
```

## Common Tasks

### Adding a New Model

1. Add model to `src/models/v1/__init__.py`
2. Add tests to `tests/test_models.py`
3. Export in `__all__`
4. Run tests: `pytest tests/test_models.py`

### Adding a New Exception

1. Add exception to `src/exceptions/v1/__init__.py`
2. Inherit from `XiansError`
3. Add tests to `tests/test_exceptions.py`
4. Export in `__all__`

### Adding a New Constant

1. Add to `src/constants/v1/__init__.py`
2. Use enums for related constants
3. Add tests to `tests/test_constants.py`
4. Export in `__all__`

## Troubleshooting

### Tests Failing

```bash
# Run tests with verbose output
pytest -vv

# Run a specific test
pytest tests/test_models.py::test_llm_config_creation -vv

# Show print statements
pytest -s
```

### Type Errors

```bash
# Run mypy on specific file
mypy src/models/v1/__init__.py

# Show detailed error messages
mypy --show-error-codes src
```

### Import Errors

```bash
# Reinstall in editable mode
pip install -e ".[dev]"

# Check installed packages
pip list | grep xians
```

## Resources

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Temporal Python SDK](https://docs.temporal.io/dev-guide/python)
- [Type Hints Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

## Getting Help

- Open an issue on GitHub
- Check existing issues and PRs
- Join our Discord community
- Email: dev@xians.ai

