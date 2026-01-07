# Xians Python SDK - User Guide

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Xians Python SDK is a **Temporal-first agent execution substrate** that provides:

- ✅ **Durable Agent Execution**: Run agents on Temporal for reliability and fault tolerance
- ✅ **Framework-Agnostic**: Use ANY agent framework (LangChain, custom code, etc.)
- ✅ **Optional Xians Server Integration**: Settings discovery, definitions registry, conversation APIs
- ✅ **Long-Running Sessions**: Support for conversational workflows with state management
- ✅ **Production-Ready**: Typed, tested, and enterprise-grade

### Key Design Principles

1. **Temporal-First**: The SDK owns workflows; you provide activities
2. **Framework-Agnostic**: No coupling to any specific agent framework
3. **Black-Box Activities**: Your agent logic is completely opaque to the SDK
4. **Xians Server is Optional**: Core functionality works standalone

---

## Installation

### Prerequisites

- Python 3.10 or higher
- Temporal server running (local or cloud)
- (Optional) Xians Server access

### Install from PyPI

```bash
pip install xians-lib-python
```

### Install from Source

```bash
git clone https://github.com/xians-platform/xians-lib-python.git
cd xians-lib-python
pip install -e .
```

### Install with Development Dependencies

```bash
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Basic Echo Agent (Minimal Example)

```python
import asyncio
from temporalio import activity
from xians.platform.v1 import (
    XiansPlatform,
    XiansOptions,
    TemporalConfig,
    LLMConfig,
    AgentRequest,
    AgentResponse,
)

# Define your agent activity (ANY framework allowed!)
@activity.defn
async def execute_agent_activity(request: AgentRequest) -> AgentResponse:
    """Your agent logic goes here - completely framework-agnostic."""
    message = request.message if isinstance(request.message, str) else str(request.message)
    return AgentResponse(text=f"Echo: {message}")

async def main():
    # Initialize platform
    platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url="https://api.xians.ai",
            api_key="your-api-key",
            temporal=TemporalConfig(
                host="localhost",
                port=7233,
                namespace="default",
            ),
            llm=LLMConfig(
                provider="openai",
                model="gpt-4",
                api_key="your-openai-key",
            ),
        )
    )

    # Register agent
    agent = platform.agents.register(
        name="EchoAgent",
        description="Simple echo agent",
        system_scoped=False,
    )

    # Define workflow
    agent.define_invoke_workflow(
        name="InvokeEcho",
        workers=2,
        activity_func=execute_agent_activity,
    )

    # Run workers (blocks until interrupted)
    await platform.run_all()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Run the Example

```bash
# Make sure Temporal is running
temporal server start-dev

# In another terminal, run your agent
python my_agent.py
```

### 3. Invoke Your Agent (from another script)

```python
from xians.platform.v1 import XiansPlatform, AgentRequest

# Connect as client (no workers)
platform = await XiansPlatform.initialize(options)
await platform.connect_temporal()

client = platform.client()

# Invoke the agent
response = await client.invoke(
    workflow_id="unique-workflow-id",
    task_queue="xians-default-user-EchoAgent-InvokeEcho",
    request=AgentRequest(
        agent_key="EchoAgent",
        message="Hello, agent!",
    ),
)

print(response.text)  # Output: "Echo: Hello, agent!"
```

---

## Core Concepts

### 1. Platform

The `XiansPlatform` is the main entry point for the SDK. It manages:
- Agent registration
- Workflow definitions
- Worker lifecycle
- Temporal connections
- Xians Server integration

```python
platform = await XiansPlatform.initialize(XiansOptions(...))
```

### 2. Agents

Agents are registered with a name and configuration:

```python
agent = platform.agents.register(
    name="MyAgent",
    description="Does something useful",
    system_scoped=False,  # True for system-wide agents
)
```

### 3. Workflows

Two workflow types are provided:

#### a) InvokeAgentWorkflow (One-Shot)
For stateless, request-response agent executions:

```python
agent.define_invoke_workflow(
    name="InvokeAgent",
    workers=2,
    activity_func=my_activity_func,
)
```

#### b) ConversationWorkflow (Long-Running)
For stateful, multi-turn conversations:

```python
agent.define_conversation_workflow(
    name="Conversation",
    workers=1,
    activity_func=my_activity_func,
)
```

### 4. Activities

Activities are where YOUR agent logic lives. The SDK treats them as black boxes:

```python
@activity.defn
async def execute_agent_activity(request: AgentRequest) -> AgentResponse:
    # Use ANY framework here:
    # - LangChain
    # - Custom code
    # - Semantic Kernel
    # - Your own implementation
    
    result = your_agent_framework.run(request.message)
    
    return AgentResponse(
        text=result,
        usage={"tokens": 100},
        model="gpt-4",
    )
```

### 5. Task Queues

Task queues are automatically named based on:
- Tenant ID (for multi-tenancy)
- System scope
- Agent key
- Workflow name

Example: `xians-tenant123-user-MyAgent-InvokeAgent`

This ensures deterministic routing for the same agent + workflow + tenant.

---

## Usage Examples

### Example 1: LangChain Agent

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from temporalio import activity

@activity.defn
async def execute_langchain_agent(request: AgentRequest) -> AgentResponse:
    """LangChain-based agent implementation."""
    
    # Initialize LangChain components
    llm = ChatOpenAI(model="gpt-4")
    agent = create_openai_functions_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)
    
    # Run agent
    result = await executor.ainvoke({"input": request.message})
    
    return AgentResponse(
        text=result["output"],
        metadata={"intermediate_steps": result.get("intermediate_steps", [])},
    )
```

### Example 2: RAG Agent with Custom Logic

```python
@activity.defn
async def execute_rag_agent(request: AgentRequest) -> AgentResponse:
    """Custom RAG implementation."""
    
    # Retrieve relevant documents
    docs = await vector_store.similarity_search(request.message, k=5)
    
    # Build context
    context = "\n".join([doc.page_content for doc in docs])
    
    # Call LLM with context
    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Context:\n{context}"},
            {"role": "user", "content": request.message},
        ],
    )
    
    return AgentResponse(
        text=response.choices[0].message.content,
        usage={
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        },
        model="gpt-4",
    )
```

### Example 3: Conversational Agent with State

```python
# Worker hosting the conversation
async def main():
    platform = await XiansPlatform.initialize(options)
    
    agent = platform.agents.register(name="ConversationalAgent")
    agent.define_conversation_workflow(
        name="Conversation",
        workers=1,
        activity_func=execute_conversational_agent,
    )
    
    await platform.run_all()

# Client interacting with conversation
async def interact():
    platform = await XiansPlatform.initialize(options)
    await platform.connect_temporal()
    client = platform.client()
    
    # Start conversation
    handle = await client.start_conversation(
        workflow_id="conv-12345",
        task_queue="xians-default-user-ConversationalAgent-Conversation",
        agent_key="ConversationalAgent",
        conversation_id="conv-12345",
    )
    
    # Send messages using update (request-response)
    response1 = await client.send_update(
        workflow_id="conv-12345",
        update_name="request_response",
        "Tell me about Temporal",
    )
    print(response1.text)
    
    response2 = await client.send_update(
        workflow_id="conv-12345",
        update_name="request_response",
        "Can you elaborate on workflows?",
    )
    print(response2.text)
    
    # Query session state
    state = await client.query(
        workflow_id="conv-12345",
        query_name="get_session_state",
    )
    print(f"Message count: {state['message_count']}")
```

### Example 4: Multi-Tenant Deployment

```python
# Register agents for different tenants
for tenant in ["acme-corp", "widgets-inc", "example-co"]:
    agent = platform.agents.register(
        name=f"Agent-{tenant}",
        system_scoped=False,
    )
    
    agent.define_invoke_workflow(
        name="TenantWorkflow",
        workers=1,
        activity_func=execute_tenant_agent,
    )

# Task queues are automatically tenant-specific:
# - xians-acme-corp-user-Agent-acme-corp-TenantWorkflow
# - xians-widgets-inc-user-Agent-widgets-inc-TenantWorkflow
# - xians-example-co-user-Agent-example-co-TenantWorkflow
```

---

## API Reference

### XiansPlatform

#### `XiansPlatform.initialize(options: XiansOptions) -> XiansPlatform`
Initialize the platform.

**Parameters:**
- `options`: Configuration options

**Returns:** Initialized platform instance

**Raises:** `ConfigurationError` if initialization fails

#### `platform.agents.register(name, description=None, system_scoped=False) -> AgentRegistration`
Register a new agent.

**Parameters:**
- `name`: Unique agent name
- `description`: Optional description
- `system_scoped`: Whether agent is system-wide

**Returns:** Agent registration for workflow configuration

#### `platform.run_all() -> None`
Start all workers and run until interrupted.

#### `platform.connect_temporal() -> None`
Connect to Temporal without starting workers (client mode).

#### `platform.client() -> AgentClient`
Get a client for invoking workflows.

#### `platform.shutdown() -> None`
Gracefully shutdown all workers and connections.

### AgentRegistration

#### `agent.define_invoke_workflow(name, workers=1, activity_func=None) -> WorkflowDefinition`
Define a one-shot invoke workflow.

#### `agent.define_conversation_workflow(name, workers=1, activity_func=None) -> WorkflowDefinition`
Define a long-running conversation workflow.

### AgentClient

#### `client.invoke(workflow_id, task_queue, request, workflow_type="InvokeAgentWorkflow", timeout=timedelta(minutes=5)) -> AgentResponse`
Invoke a one-shot agent execution.

#### `client.start_conversation(workflow_id, task_queue, agent_key, conversation_id, workflow_type="ConversationWorkflow") -> WorkflowHandle`
Start a long-running conversation workflow.

#### `client.send_signal(workflow_id, signal_name, *args) -> None`
Send a signal to a running workflow (fire-and-forget).

#### `client.send_update(workflow_id, update_name, *args) -> Any`
Send an update to a running workflow (request-response).

#### `client.query(workflow_id, query_name, *args) -> Any`
Query a running workflow's state.

#### `client.cancel_workflow(workflow_id) -> None`
Cancel a running workflow.

### Models

#### AgentRequest
```python
AgentRequest(
    agent_key: str,
    message: str | dict,
    conversation_id: str | None = None,
    metadata: dict = {},
    tenant_id: str | None = None,
    system_scoped: bool = False,
    idempotency_key: str | None = None,
    timestamp: datetime = now(),
)
```

#### AgentResponse
```python
AgentResponse(
    text: str | None = None,
    payload: dict | None = None,
    raw: Any | None = None,
    usage: dict | None = None,
    model: str | None = None,
    metadata: dict = {},
)
```

---

## Best Practices

### 1. Activity Design

✅ **DO:**
- Keep activities focused and single-purpose
- Use proper error handling
- Return structured responses
- Log important events
- Use idempotency keys for critical operations

❌ **DON'T:**
- Put I/O in workflow code (only in activities)
- Store large state in workflows
- Use non-deterministic operations in workflows

### 2. Workflow Configuration

✅ **DO:**
- Use meaningful workflow and agent names
- Configure appropriate timeouts
- Set retry policies for activities
- Use task queues for routing control

❌ **DON'T:**
- Use the same workflow ID for different executions
- Set timeouts too short for long-running operations

### 3. Error Handling

```python
@activity.defn
async def execute_agent_activity(request: AgentRequest) -> AgentResponse:
    try:
        result = await agent.run(request.message)
        return AgentResponse(text=result)
    except ValueError as e:
        # Return error as response (don't raise)
        return AgentResponse(
            text=f"Invalid input: {str(e)}",
            metadata={"error": True, "error_type": "ValueError"},
        )
    except Exception as e:
        activity.logger.error(f"Agent failed: {e}")
        # Raise to trigger Temporal retry
        raise
```

### 4. Resource Management

```python
async def main():
    platform = await XiansPlatform.initialize(options)
    
    try:
        # Register and run
        agent = platform.agents.register(...)
        agent.define_invoke_workflow(...)
        await platform.run_all()
    finally:
        # Always cleanup
        await platform.shutdown()
```

---

## Troubleshooting

### Common Issues

#### 1. "Authentication failed (401 Unauthorized)"

**Cause:** Invalid, expired, or missing API key.

**Solution:**
1. **Verify API key is set correctly:**
   ```python
   from xians.platform.v1 import XiansOptions
   
   options = XiansOptions(
       server_url="https://api.agentri.ai",
       api_key="your-actual-api-key-here",  # NOT a placeholder!
       llm=...,
   )
   ```

2. **Check API key validity:**
   - Log in to your Xians dashboard
   - Navigate to Settings → API Keys
   - Verify the key exists and hasn't expired
   - Generate a new key if needed

3. **Verify environment variables (if using):**
   ```bash
   # If loading from environment
   echo $XIANS_API_KEY
   ```
   ```python
   import os
   from pydantic import SecretStr
   
   options = XiansOptions(
       server_url="https://api.agentri.ai",
       api_key=SecretStr(os.environ["XIANS_API_KEY"]),
       llm=...,
   )
   ```

4. **Enable debug logging to verify configuration:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   
   # You should see:
   # DEBUG:xians.interfaces.v1.xians_client:Initializing XiansServerClient with server_url=...
   ```

5. **Test API key manually:**
   ```python
   import httpx
   
   async def test_api_key():
       async with httpx.AsyncClient() as client:
           response = await client.get(
               "https://api.agentri.ai/api/agent/settings/flowserver",
               headers={"X-API-Key": "your-api-key"},
           )
           print(f"Status: {response.status_code}")
           if response.status_code == 200:
               print("✅ API key is valid!")
           else:
               print(f"❌ Error: {response.text}")
   ```

#### 2. "Temporal client not initialized"

**Cause:** Trying to get client before connecting to Temporal.

**Solution:**
```python
await platform.connect_temporal()  # or
await platform.run_all()
```

#### 3. Workflow not found

**Cause:** Task queue mismatch or workers not started.

**Solution:**
- Verify task queue name matches
- Ensure workers are running
- Check `build_task_queue_name()` output

#### 4. Activity timeout

**Cause:** Activity takes longer than configured timeout.

**Solution:**
```python
# Increase timeout in workflow definition
response = await workflow.execute_activity(
    activity_name,
    request,
    start_to_close_timeout=timedelta(minutes=10),  # Increase this
)
```

#### 5. "Failed to fetch Temporal settings"

**Cause:** Xians Server not accessible or API key invalid.

**Solution:**
```python
# Provide Temporal config directly
XiansOptions(
    server_url="...",
    api_key="...",
    temporal=TemporalConfig(  # Don't fetch from server
        host="localhost",
        port=7233,
        namespace="default",
    ),
    llm=...,
)
```

### Temporal TLS Configuration (Private CA, mTLS, SNI)

The Python SDK supports secure connections to Temporal using TLS, including:
- Public CA TLS
- Private CA TLS (custom root CA)
- Mutual TLS (client certificate + private key)
- SNI/domain override (certificate hostname mismatch)

### Config models

Use `TemporalConfig` with nested `TemporalTLSConfig`:
- `address`: "host:port"
- `namespace`: Temporal namespace
- `tls.enabled`: enable TLS (auto-inferred if any TLS field is provided)
- `tls.root_ca_pem` or `tls.root_ca_path`: custom Root CA (PEM string or file path)
- `tls.client_cert_pem` / `tls.client_cert_path`: client certificate (PEM or path)
- `tls.client_key_pem` / `tls.client_key_path`: client private key (PEM or path)
- `tls.domain`: SNI override when certificate hostname differs from target address
- `tls.pem_is_base64`: set True if PEM strings are base64-encoded

### Examples

Private CA + SNI override:

```python
from xians.models.v1.configs import TemporalConfig, TemporalTLSConfig

temporal = TemporalConfig(
    address="temporal.mycorp.internal:7233",
    namespace="default",
    tls=TemporalTLSConfig(
        root_ca_path="/etc/ssl/mycorp-root-ca.pem",
        domain="temporal.mycorp.internal",
    ),
)
```

Mutual TLS (client cert + key) with private CA:

```python
temporal = TemporalConfig(
    address="temporal.mycorp.internal:7233",
    namespace="default",
    tls=TemporalTLSConfig(
        root_ca_path="/etc/ssl/mycorp-root-ca.pem",
        client_cert_path="/etc/ssl/client.crt",
        client_key_path="/etc/ssl/client.key",
        domain="temporal.mycorp.internal",
    ),
)
```

Base64 PEM inputs (from server or environment):

```python
import os

temporal = TemporalConfig(
    address=os.getenv("XIANS_TEMPORAL_ADDRESS", "temporal.mycorp.internal:7233"),
    namespace=os.getenv("XIANS_TEMPORAL_NAMESPACE", "default"),
    tls=TemporalTLSConfig(
        root_ca_pem=os.getenv("XIANS_TEMPORAL_TLS_ROOT_CA_PEM"),
        client_cert_pem=os.getenv("XIANS_TEMPORAL_TLS_CLIENT_CERT_PEM"),
        client_key_pem=os.getenv("XIANS_TEMPORAL_TLS_CLIENT_KEY_PEM"),
        pem_is_base64=True,
        domain=os.getenv("XIANS_TEMPORAL_TLS_DOMAIN"),
    ),
)
```

### Server-provided settings

If you do not pass `XiansOptions.temporal`, the SDK will fetch Temporal settings from Xians Server and build a `TemporalConfig` automatically. Supported server fields:
- `flowServerUrl` (or `TEMPORAL_SERVER_URL` env override)
- `flowServerNamespace`
- `flowServerRootCaPem` (optional)
- `flowServerCertBase64` (optional, client cert)
- `flowServerPrivateKeyBase64` (optional, client key)
- `flowServerDomainOverride` / `flowServerSniDomain` (optional)

The SDK logs a summary of TLS presence (enabled, root CA provided, mTLS provided, domain override) without logging sensitive material.

### Troubleshooting UnknownIssuer / SNI

If you see `InvalidCertificate(UnknownIssuer)` or `CERTIFICATE_VERIFY_FAILED`:
- Provide a private Root CA via `TemporalTLSConfig.root_ca_pem` or `root_ca_path`.
- If the certificate hostname doesn’t match the address, set `TemporalTLSConfig.domain` to the certificate’s CN/SAN.
- If the server requires mutual TLS, set BOTH `client_cert_*` and `client_key_*`.
- Ensure PEM values are correct (BEGIN/END blocks) and files are readable with proper permissions.

The SDK error message includes:
- target address and namespace
- TLS enabled, root CA provided, mTLS provided, domain override
- actionable hints based on the underlying error

### Security note

Do NOT skip TLS verification unless explicitly directed by your security policy. The SDK does not disable verification by default and does not provide a "skip verify" option.

---

## Next Steps

- 📚 Read [Development Guide](./DEVELOPMENT_GUIDE.md) to contribute
- 🔧 Check [API Documentation](./API.md) for detailed reference
- 🎯 See [Examples](../examples/) for more use cases
- 🏗️ Review [Architecture](./ARCHITECTURE.md) for design details

---

**Happy Building! 🚀**
