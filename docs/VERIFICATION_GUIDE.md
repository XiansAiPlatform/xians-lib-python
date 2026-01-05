# Library Verification Guide

This guide provides multiple ways to verify that the Xians Python SDK is working correctly.

## Table of Contents
1. [Quick Verification](#quick-verification)
2. [Detailed Testing](#detailed-testing)
3. [Manual Testing](#manual-testing)
4. [Import Verification](#import-verification)
5. [Troubleshooting](#troubleshooting)

---

## Quick Verification

### 1. Run All Tests (Recommended)

```bash
cd "/Users/poornimaka/Library/CloudStorage/OneDrive-99x/Xians Platform/pythonLib/xians-lib-python"
python -m pytest tests/ -v
```

**Expected Result:** All 37 tests should pass
```
tests/test_constants.py ........    [21%]
tests/test_exceptions.py .......   [40%]
tests/test_models.py ..............  [78%]
tests/test_utils.py ........        [100%]

37 passed
```

### 2. Run CI Pipeline

```bash
./scripts/ci.sh
```

This runs:
- Code formatting check
- Linting (ruff + mypy)
- Full test suite with coverage

**Expected Result:** All checks pass, ~68% code coverage

### 3. Quick Import Test

```bash
python -c "
from src.models.v1 import LLMMessage, AgentDefinition, WorkflowDefinition
from src.constants.v1 import LLMProvider, WorkflowType
from src.utils.v1 import compute_hash, safe_dict_get

print('✅ All core imports working!')
print(f'✅ LLM Providers: {[p.value for p in LLMProvider]}')
print(f'✅ Workflow Types: {[w.value for w in WorkflowType]}')
"
```

**Expected Output:**
```
✅ All core imports working!
✅ LLM Providers: ['openai', 'anthropic', 'azure_openai', 'custom']
✅ Workflow Types: ['Conversational', 'TaskBased', 'Reactive', 'Custom']
```

---

## Detailed Testing

### Test by Category

#### Unit Tests Only
```bash
pytest tests/ -m unit -v
```

#### Test Specific Modules

**Test Models:**
```bash
pytest tests/test_models.py -v
```

**Test Utils:**
```bash
pytest tests/test_utils.py -v
```

**Test Constants:**
```bash
pytest tests/test_constants.py -v
```

**Test Exceptions:**
```bash
pytest tests/test_exceptions.py -v
```

#### Test with Coverage Report

```bash
pytest --cov=src --cov-report=term-missing --cov-report=html
```

Then open `htmlcov/index.html` to see detailed coverage.

#### Test Specific Functionality

**Test Pydantic Models:**
```bash
pytest tests/test_models.py::test_llm_config_required_fields -v
pytest tests/test_models.py::test_agent_definition -v
pytest tests/test_models.py::test_workflow_definition -v
```

**Test Utilities:**
```bash
pytest tests/test_utils.py::test_compute_hash -v
pytest tests/test_utils.py::test_safe_dict_get_nested -v
```

---

## Manual Testing

### 1. Test Pydantic Models

Create a test script `test_models_manual.py`:

```python
"""Manual test script for Pydantic models."""
from pydantic import SecretStr
from src.models.v1 import (
    LLMConfig,
    XiansOptions,
    AgentDefinition,
    WorkflowDefinition,
    LLMMessage,
    LLMResponse,
)
from src.constants.v1 import LLMProvider, WorkflowType, MessageRole

def test_llm_config():
    """Test LLM configuration."""
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
        api_key=SecretStr("sk-test123"),
        temperature=0.8,
    )
    print(f"✅ LLM Config: {config.provider.value} - {config.model}")
    print(f"   Temperature: {config.temperature}")
    assert config.provider == LLMProvider.OPENAI
    assert config.temperature == 0.8

def test_xians_options():
    """Test Xians options."""
    options = XiansOptions(
        server_url="https://api.xians.ai",
        api_key=SecretStr("test-key"),
        llm=LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4"),
        log_level="DEBUG",
    )
    print(f"✅ Xians Options: {options.server_url}")
    print(f"   Log Level: {options.log_level}")
    assert options.log_level == "DEBUG"

def test_agent_definition():
    """Test agent definition."""
    agent = AgentDefinition(
        name="Test Agent",
        description="A test agent",
        system_scoped=True,
        metadata={"version": "1.0", "author": "test"},
    )
    print(f"✅ Agent: {agent.name}")
    print(f"   System Scoped: {agent.system_scoped}")
    print(f"   Metadata: {agent.metadata}")
    assert agent.name == "Test Agent"

def test_workflow_definition():
    """Test workflow definition."""
    workflow = WorkflowDefinition(
        workflow_type=WorkflowType.CONVERSATIONAL,
        name="Chat Workflow",
        workers=3,
    )
    print(f"✅ Workflow: {workflow.name}")
    print(f"   Type: {workflow.workflow_type.value}")
    print(f"   Workers: {workflow.workers}")
    assert workflow.workers == 3

def test_llm_message():
    """Test LLM message."""
    msg = LLMMessage(
        role=MessageRole.USER,
        content="Hello, AI!",
        name="User123",
    )
    print(f"✅ Message: {msg.role.value} - {msg.content}")
    assert msg.role == MessageRole.USER

def test_llm_response():
    """Test LLM response."""
    response = LLMResponse(
        text="Hello! How can I help?",
        model="gpt-4",
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    )
    print(f"✅ Response: {response.text}")
    print(f"   Model: {response.model}")
    print(f"   Tokens: {response.usage['total_tokens']}")
    assert response.usage["total_tokens"] == 30

if __name__ == "__main__":
    print("\n🧪 Testing Pydantic Models\n" + "="*50)
    
    test_llm_config()
    print()
    test_xians_options()
    print()
    test_agent_definition()
    print()
    test_workflow_definition()
    print()
    test_llm_message()
    print()
    test_llm_response()
    
    print("\n" + "="*50)
    print("✅ All manual tests passed!")
```

Run it:
```bash
python test_models_manual.py
```

### 2. Test Utility Functions

Create `test_utils_manual.py`:

```python
"""Manual test script for utility functions."""
from src.utils.v1 import compute_hash, safe_dict_get, setup_logging

def test_compute_hash():
    """Test hashing functionality."""
    content = "Hello, World!"
    hash1 = compute_hash(content)
    hash2 = compute_hash(content)
    
    print(f"✅ Hash (consistent): {hash1}")
    print(f"   Length: {len(hash1)} characters")
    assert hash1 == hash2
    assert len(hash1) == 64

def test_safe_dict_get():
    """Test safe dictionary access."""
    data = {
        "user": {
            "profile": {
                "name": "John Doe",
                "email": "john@example.com"
            }
        }
    }
    
    name = safe_dict_get(data, "user", "profile", "name")
    email = safe_dict_get(data, "user", "profile", "email")
    missing = safe_dict_get(data, "user", "settings", "theme", default="dark")
    
    print(f"✅ Nested access:")
    print(f"   Name: {name}")
    print(f"   Email: {email}")
    print(f"   Missing (with default): {missing}")
    
    assert name == "John Doe"
    assert missing == "dark"

def test_logging():
    """Test logging setup."""
    logger = setup_logging(level="INFO", name="test-logger")
    
    print(f"✅ Logger configured:")
    print(f"   Name: {logger.name}")
    print(f"   Level: {logger.level}")
    
    # Test logging
    logger.info("This is an info message")
    logger.debug("This debug message won't show (level=INFO)")
    
    assert logger.name == "test-logger"

if __name__ == "__main__":
    print("\n🧪 Testing Utility Functions\n" + "="*50)
    
    test_compute_hash()
    print()
    test_safe_dict_get()
    print()
    test_logging()
    
    print("\n" + "="*50)
    print("✅ All utility tests passed!")
```

Run it:
```bash
python test_utils_manual.py
```

### 3. Test Constants and Enums

Create `test_constants_manual.py`:

```python
"""Manual test script for constants and enums."""
from src.constants.v1 import (
    LLMProvider,
    WorkflowType,
    MessageRole,
    AgentStatus,
    WorkflowStatus,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_MAX_TOKENS,
    XIANS_AGENT_PATH,
)

def test_enums():
    """Test all enum types."""
    print("✅ LLM Providers:")
    for provider in LLMProvider:
        print(f"   - {provider.name}: {provider.value}")
    
    print("\n✅ Workflow Types:")
    for wf_type in WorkflowType:
        print(f"   - {wf_type.name}: {wf_type.value}")
    
    print("\n✅ Message Roles:")
    for role in MessageRole:
        print(f"   - {role.name}: {role.value}")
    
    print("\n✅ Agent Statuses:")
    for status in AgentStatus:
        print(f"   - {status.name}: {status.value}")
    
    print("\n✅ Workflow Statuses:")
    for status in WorkflowStatus:
        print(f"   - {status.name}: {status.value}")

def test_constants():
    """Test constant values."""
    print("\n✅ Default Constants:")
    print(f"   Temperature: {DEFAULT_LLM_TEMPERATURE}")
    print(f"   Max Tokens: {DEFAULT_LLM_MAX_TOKENS}")
    print(f"   Agent Path: {XIANS_AGENT_PATH}")
    
    assert DEFAULT_LLM_TEMPERATURE == 0.7
    assert DEFAULT_LLM_MAX_TOKENS == 2048

if __name__ == "__main__":
    print("\n🧪 Testing Constants and Enums\n" + "="*50)
    test_enums()
    test_constants()
    print("\n" + "="*50)
    print("✅ All constants verified!")
```

Run it:
```bash
python test_constants_manual.py
```

---

## Import Verification

### Test All Core Imports

Create `test_imports.py`:

```python
"""Verify all core imports work correctly."""

def test_imports():
    """Test all major imports."""
    print("Testing imports...")
    
    # Constants
    from src.constants.v1 import (
        LLMProvider, WorkflowType, MessageRole, AgentStatus, WorkflowStatus,
        DEFAULT_LLM_TEMPERATURE, DEFAULT_LLM_MAX_TOKENS,
    )
    print("✅ Constants imported")
    
    # Exceptions
    from src.exceptions.v1 import (
        XiansError, ConfigurationError, XiansServerError,
        LLMError, ResourceNotFoundError, AuthenticationError,
    )
    print("✅ Exceptions imported")
    
    # Models
    from src.models.v1 import (
        TemporalConfig, LLMConfig, XiansOptions,
        LLMMessage, LLMResponse, AgentDefinition, WorkflowDefinition,
    )
    print("✅ Models imported")
    
    # Utils
    from src.utils.v1 import (
        compute_hash, safe_dict_get, setup_logging, create_retry_decorator,
    )
    print("✅ Utils imported")
    
    # Temporal workflows
    from src.temporal_workflows.v1 import (
        BaseWorkflow, ConversationalWorkflow, TaskBasedWorkflow,
    )
    print("✅ Temporal workflows imported")
    
    print("\n✅ All imports successful!")

if __name__ == "__main__":
    test_imports()
```

Run it:
```bash
python test_imports.py
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Ensure you're in the right directory
cd "/Users/poornimaka/Library/CloudStorage/OneDrive-99x/Xians Platform/pythonLib/xians-lib-python"

# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall in editable mode
pip install -e ".[dev]"
```

#### 2. Test Failures
```bash
# Run tests with verbose output to see details
pytest tests/ -vv

# Run with traceback
pytest tests/ --tb=long

# Run specific failing test
pytest tests/test_models.py::test_llm_config_required_fields -vv
```

#### 3. Missing Dependencies
```bash
# Check installed packages
pip list | grep -E "(pydantic|temporalio|httpx|pytest)"

# Reinstall dependencies
pip install -r requirements.txt  # if exists
# or
pip install -e ".[dev]"
```

#### 4. Module Not Found
```bash
# Verify PYTHONPATH
echo $PYTHONPATH

# Add current directory to path (temporary)
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use the src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### Verification Checklist

- [ ] All 37 tests pass (`pytest tests/ -v`)
- [ ] Code formatting check passes (`black --check src tests`)
- [ ] Linting passes (`ruff check src tests`)
- [ ] Type checking passes (`mypy src`)
- [ ] All core imports work
- [ ] Coverage >= 68%
- [ ] No import errors
- [ ] No runtime errors in manual tests

---

## Summary

The library is considered **working** if:

1. ✅ **All 37 unit tests pass** - Core functionality verified
2. ✅ **68%+ code coverage** - Adequate test coverage
3. ✅ **No import errors** - All modules load correctly
4. ✅ **Type checking passes** - Type safety verified
5. ✅ **Code style compliant** - PEP 8 + Black formatting
6. ✅ **Pydantic models validate correctly** - Data validation works
7. ✅ **Utility functions work** - Helper functions operational

### Quick Health Check Command

```bash
cd "/Users/poornimaka/Library/CloudStorage/OneDrive-99x/Xians Platform/pythonLib/xians-lib-python" && \
python -m pytest tests/ -v --tb=short && \
echo "✅ Library is working correctly!"
```

If this passes, **your library is fully functional**! 🎉

