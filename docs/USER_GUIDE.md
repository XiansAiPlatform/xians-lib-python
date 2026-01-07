# Xians Python SDK - User Guide

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuring the SDK](#configuring-the-sdk)
- [Core Concepts](#core-concepts)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Xians Server Integration API](#xians-server-integration-api)
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
    # Initialize platform (NO LLM config needed!)
    platform = await XiansPlatform.initialize(
        XiansOptions(
            server_url="https://api.xians.ai",
            api_key="your-api-key",
            temporal=TemporalConfig(
                host="localhost",
                port=7233,
                namespace="default",
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
import asyncio
from datetime import timedelta
from xians.platform.v1 import XiansPlatform, AgentRequest, XiansOptions
from xians.models.v1.configs import TemporalConfig

async def main():
    # Connect as client (no workers)
    # Note: You can use simple strings - the SDK handles type conversion automatically
    options = XiansOptions(
        server_url="https://api.xians.ai",  # Plain string works!
        api_key="<base64 bearer cert>",  # Plain string works!
        temporal=TemporalConfig(address="localhost:7233", namespace="default"),
    )

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
        timeout=timedelta(minutes=5),
    )

    print(response.text)  # Output: "Echo: Hello, agent!"

    await platform.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Configuring the SDK

This section explains how to configure the SDK using the Pydantic v2 models defined in `src/xians/models/v1/configs.py`. The central entry point is `XiansOptions`, which aggregates server and Temporal settings.

> **💡 Pro Tip:** You can use simple strings for most configuration fields! The SDK automatically converts plain strings to the appropriate types (`SecretStr`, `HttpUrl`). This makes configuration more intuitive while maintaining type safety internally.

> **⚠️ Important Change:** The `llm` parameter is **deprecated** and no longer required. LLM configuration and invocation should be handled entirely in your activity implementation. The SDK does not validate, store, or transmit LLM configuration.

### XiansOptions (Top-level)

```python
from xians.models.v1.configs import XiansOptions, TemporalConfig

# Simple string usage - SDK handles type conversion automatically!
options = XiansOptions(
    server_url="https://api.xians.ai",  # Plain string → HttpUrl
    api_key="<base64-bearer-cert>",  # Plain string → SecretStr
    server_auth_mode="bearer_cert",  # default
    server_x_api_key=None,
    tenant_id="acme",
    temporal=TemporalConfig(
        address="temporal.example.com:7233",
        namespace="prod",
        task_queue="xians-agents",
    ),
    log_level="INFO",
    enable_structured_logging=False,
)
```

Key behaviors:
- `server_auth_mode` supports `"bearer_cert"` (default) and `"x_api_key"` with case-insensitive normalization.
- `api_key` is an alias for `server_api_key` and is stored as `SecretStr`.
- `llm` parameter is **deprecated** - configure LLM in your activities instead.
- Validation rejects empty or obviously placeholder credentials.
- `log_level` is normalized to uppercase and must be one of `DEBUG, INFO, WARNING, ERROR, CRITICAL`.

### TemporalConfig

```python
from xians.models.v1.configs import TemporalConfig, TemporalTLSConfig

temporal_cfg = TemporalConfig(
    # You can specify address directly
    address="localhost:7233",
    namespace="default",
    task_queue="xians-agents",

    # Or use backward-compatible host/port
    host="localhost",
    port=7233,

    # Optional TLS
    tls=TemporalTLSConfig(
        enabled=True,
        root_ca_path="/etc/ssl/certs/ca.pem",
        # For mTLS, provide both cert and key (pair validation enforced)
        client_cert_path="/etc/ssl/certs/client.crt",
        client_key_path="/etc/ssl/private/client.key",
        domain="temporal.example.com",  # SNI override
        pem_is_base64=False,
    ),
)
```

Important:
- If `address` is not provided but `host` is, it composes `address` as `host:port` (default port `7233`).
- Legacy TLS fields from older configs are automatically migrated into `tls` when present.
- mTLS requires both client certificate and private key; validation will raise if one is missing.

### TemporalTLSConfig

```python
from xians.models.v1.configs import TemporalTLSConfig

tls_cfg = TemporalTLSConfig(
    enabled=True,  # inferred True if any TLS material is present
    root_ca_pem="<PEM string>",
    client_cert_pem="<PEM string>",
    client_key_pem="<PEM string>",
    domain="temporal.example.com",
    pem_is_base64=True,  # if your PEM inputs are base64-encoded blobs
)
```

Notes:
- Set `pem_is_base64=True` when passing base64-encoded PEM strings; the SDK will decode before use.
- You may mix `*_pem` and `*_path` forms. If any TLS material is provided, `enabled` is inferred `True`.

### LLMConfig

> **⚠️ DEPRECATED:** The `LLMConfig` model is no longer required by `XiansOptions`. LLM configuration and invocation should be handled entirely within your activity implementation. You can use any LLM library (OpenAI SDK, Anthropic SDK, LangChain, etc.) directly in your activities.

The `LLMConfig` model is still available for your own use if you want structured LLM configuration in your application:

```python
from xians.models.v1.configs import LLMConfig

# You can still use LLMConfig in YOUR application code (not for SDK initialization)
llm_cfg = LLMConfig(
    provider="openai",  # Plain string → LLMProvider enum
    model="gpt-4o",
    api_key="<provider key>",  # Plain string → SecretStr
    api_base="https://api.openai.com/v1",  # Plain string → HttpUrl
    temperature=0.3,
    max_tokens=1024,
    timeout_seconds=30,
    extra_params={"frequency_penalty": 0.2},
)

# Use it in your activity:
@activity.defn
async def my_agent_activity(request: AgentRequest) -> AgentResponse:
    # Load your LLM config from environment or config file
    import openai
    openai.api_key = llm_cfg.api_key.get_secret_value()
    
    response = openai.ChatCompletion.create(
        model=llm_cfg.model,
        messages=[{"role": "user", "content": request.message}],
        temperature=llm_cfg.temperature,
    )
    return AgentResponse(text=response.choices[0].message.content)
```

Validation:
- `temperature` must be between `0.0` and `2.0`.
- `max_tokens >= 1`, `timeout_seconds >= 1`.
- `extra_params` lets you pass provider-specific options (e.g., `top_p`, penalties).
- The `provider` field accepts plain strings and converts them to `LLMProvider` enum automatically (case-insensitive).

### XiansServerConfig (optional direct use)

While `XiansOptions` is the primary entry point, some advanced scenarios use `XiansServerConfig` directly.

```python
from xians.models.v1.configs import XiansServerConfig

# Simple string usage - SDK handles type conversion
server_cfg = XiansServerConfig(
    server_url="https://api.xians.ai",  # Plain string → HttpUrl
    auth_mode="bearer_cert",  # or "x_api_key"
    api_key="<base64 cert>",  # Plain string → SecretStr (alias for bearer_cert_base64)
    x_api_key=None,
    tenant_id="acme",
    timeout_seconds=30,
    retry_attempts=3,
    verify_ssl=True,
)
```

Validation:
- `auth_mode` requires the corresponding credential (`bearer_cert_base64` or `x_api_key`).
- Secrets are validated for non-empty and minimum length; placeholder-looking values are rejected.

### Configuration via Environment Variables

You can externalize secrets and settings using environment variables with a small wrapper around `XiansOptions`. We recommend `pydantic-settings` for enterprise apps.

```python
from pydantic_settings import BaseSettings
from pydantic import SecretStr, AnyUrl
from xians.models.v1.configs import XiansOptions, TemporalConfig, TemporalTLSConfig, LLMConfig

class AppSettings(BaseSettings):
    server_url: AnyUrl
    api_key: SecretStr | None = None
    server_auth_mode: str = "bearer_cert"
    server_x_api_key: SecretStr | None = None
    tenant_id: str | None = None

    temporal_address: str | None = None
    temporal_namespace: str = "default"
    temporal_task_queue: str = "xians-agents"

    temporal_tls_enabled: bool = False
    temporal_tls_root_ca_path: str | None = None
    temporal_tls_client_cert_path: str | None = None
    temporal_tls_client_key_path: str | None = None
    temporal_tls_domain: str | None = None

    # Note: LLM config is NO LONGER part of XiansOptions
    # Configure LLM in your activities instead
    # llm_provider: str  # DEPRECATED - remove from XiansOptions
    # llm_model: str     # DEPRECATED - remove from XiansOptions

    class Config:
        env_prefix = "XIANS_"
        case_sensitive = False

settings = AppSettings()  # loads from env

options = XiansOptions(
    server_url=settings.server_url,
    api_key=settings.api_key,
    server_auth_mode=settings.server_auth_mode,
    server_x_api_key=settings.server_x_api_key,
    tenant_id=settings.tenant_id,
    temporal=TemporalConfig(
        address=settings.temporal_address or "localhost:7233",
        namespace=settings.temporal_namespace,
        task_queue=settings.temporal_task_queue,
        tls=TemporalTLSConfig(
            enabled=settings.temporal_tls_enabled,
            root_ca_path=settings.temporal_tls_root_ca_path,
            client_cert_path=settings.temporal_tls_client_cert_path,
            client_key_path=settings.temporal_tls_client_key_path,
            domain=settings.temporal_tls_domain,
        ) if settings.temporal_tls_enabled else None,
    ),
    # llm parameter removed - configure LLM in your activities
)
```

Example environment variables:

```bash
export XIANS_SERVER_URL="https://api.xians.ai"
export XIANS_API_KEY="<base64 bearer cert>"
export XIANS_SERVER_AUTH_MODE="bearer_cert"
export XIANS_TENANT_ID="acme"

export XIANS_TEMPORAL_ADDRESS="temporal.example.com:7233"
export XIANS_TEMPORAL_NAMESPACE="prod"
export XIANS_TEMPORAL_TASK_QUEUE="xians-agents"

# LLM configuration is now handled in YOUR activities
# You can load these in your activity implementation:
# export OPENAI_API_KEY="<openai key>"
# export ANTHROPIC_API_KEY="<anthropic key>"
```

### Security and Validation Tips

- Never hardcode secrets in source code. Load via environment variables or secret managers.
- `XiansOptions` and `XiansServerConfig` validate secrets and reject placeholders.
- Prefer using TLS for Temporal connections in production; enable mTLS when possible.
- Ensure `verify_ssl=True` when calling the Xians Server.
- Keep `log_level` appropriate for production (typically `INFO` or `WARNING`).

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

## Xians Server Integration

The SDK provides typed APIs for integrating with Xians Server for workflow definitions, conversation management, usage reporting, knowledge base operations, and document storage. All server interactions use strict payload validation and camelCase JSON serialization.

### Prerequisites

- Access to a Xians Server instance
- Valid API key configured in `XiansOptions`
- Server URL configured in `XiansOptions`

### Flow Definition Upload

Upload workflow definitions to Xians Server for registration and discovery.

```python
from xians.models.v1.server_contracts import (
    ParameterDefinition,
    ActivityDefinitionRequest,
    FlowDefinitionRequest,
)

# Create parameter definitions
param = ParameterDefinition(
    name="input_message",
    type="string",
)

# Create activity definitions
activity = ActivityDefinitionRequest(
    activity_name="process_message",
    knowledge_ids=["kb_001"],
    parameter_definitions=[param],
)

# Create flow definition
flow = FlowDefinitionRequest(
    agent="MyAgent",
    workflow_type="Conversational",
    activity_definitions=[activity],
    parameter_definitions=[param],
    system_scoped=False,
)

# Upload to server
response = await platform.server_client.upload_flow_definition(flow)
```

**Validation Rules:**
- `agent` - required, non-empty string
- `workflowType` - required, non-empty string
- `activityDefinitions` - required, minimum 1 element
- `parameterDefinitions` - required, minimum 1 element

### Outbound Conversation Messages

Send conversation updates back to participants through Xians Server.

#### Send Chat Message

```python
from xians.models.v1.server_contracts import ChatOrDataRequest

request = ChatOrDataRequest(
    participant_id="user_123",
    workflow_id="workflow_456",
    text="Hello! How can I help you today?",
)

response = await platform.server_client.send_outbound_chat(request)
```

#### Send Data Payload

```python
request = ChatOrDataRequest(
    participant_id="user_123",
    data={
        "action": "update_status",
        "status": "completed",
        "details": {"processed_items": 42}
    },
)

response = await platform.server_client.send_outbound_data(request)
```

#### Send Webhook Event

```python
request = ChatOrDataRequest(
    participant_id="user_123",
    data={"event": "conversation_milestone", "milestone": "halfway"},
)

response = await platform.server_client.send_outbound_webhook(request)
```

#### Send Handoff

```python
from xians.models.v1.server_contracts import HandoffRequest

request = HandoffRequest(
    participant_id="user_123",
    target="human_agent",
    reason="Complex issue requires human expertise",
    text="Connecting you with a specialist...",
)

response = await platform.server_client.send_handoff(request)
```

### Usage Reporting

Report LLM token usage and performance metrics to Xians Server.

```python
from xians.models.v1.server_contracts import UsageReportRequest

usage = UsageReportRequest(
    model="gpt-4",
    workflow_id="workflow_456",
    request_id="req_789",
    source="openai",
    prompt_tokens=150,
    completion_tokens=75,
    total_tokens=225,
    message_count=3,
    response_time_ms=1200,
    metadata={"region": "us-east-1", "batch_size": 1},
)

response = await platform.server_client.report_usage(usage)
```

**Validation Rules:**
- All token counts (`promptTokens`, `completionTokens`, `totalTokens`, `messageCount`) must be integers >= 0
- Warning logged if all counts are 0

### Knowledge Base Management

Query, retrieve, and manage knowledge bases registered with Xians Server.

#### Get Latest Knowledge

```python
kb = await platform.server_client.get_latest_knowledge(
    name="product_faq",
    agent="MyAgent",
)
```

#### List All Knowledge

```python
all_knowledge = await platform.server_client.list_knowledge(agent="MyAgent")
```

#### Create Knowledge

```python
kb = await platform.server_client.create_knowledge(
    name="product_faq",
    agent="MyAgent",
    type="document",
    content="Q: What is your product? A: It helps...",
)
```

#### Delete Knowledge

```python
response = await platform.server_client.delete_knowledge(
    name="product_faq",
    agent="MyAgent",
)
```

### Document Management

Store and retrieve documents through Xians Server's document API.

#### Save Document

```python
document = {
    "title": "User Profile",
    "user_id": "user_123",
    "email": "user@example.com",
}

response = await platform.server_client.save_document(
    document=document,
    options={"index": True, "ttl": 3600},
)
```

#### Get Document by ID

```python
doc = await platform.server_client.get_document(id="doc_789")
```

#### Get Document by Key

```python
doc = await platform.server_client.get_document_by_key(
    type="user_profile",
    key="user_123",
)
```

#### Query Documents

```python
results = await platform.server_client.query_documents(
    query={"status": "active", "type": "conversation"},
    content_type="application/json",
)
```

#### Update Document

```python
updated_doc = {"id": "doc_789", "title": "Updated Title"}
response = await platform.server_client.update_document(
    document=updated_doc,
    options={"merge": True},
)
```

#### Delete Document

```python
response = await platform.server_client.delete_document(id="doc_789")
```

#### Delete Multiple Documents

```python
response = await platform.server_client.delete_many_documents(
    ids=["doc_789", "doc_790", "doc_791"]
)
```

#### Check Document Existence

```python
result = await platform.server_client.document_exists(id="doc_789")
# Returns: {"exists": true}
```

### Error Handling

All server calls raise `XiansServerError` on failure. Errors include full context:

```python
from xians.exceptions.v1.errors import XiansServerError

try:
    response = await platform.server_client.upload_flow_definition(flow)
except XiansServerError as e:
    print(f"Status: {e.status_code}")
    print(f"Method: {e.method}")
    print(f"URL: {e.url}")
    print(f"Response: {e.response_body}")
    
    # Special handling for validation errors
    if e.status_code == 400:
        print("Payload validation failed - check required fields")
```

### Complete Example: Conversational Agent with Server Integration

```python
import asyncio
from temporalio import activity
from xians.platform.v1 import XiansPlatform, XiansOptions, TemporalConfig
from xians.models.v1.server_contracts import (
    ChatOrDataRequest,
    UsageReportRequest,
    FlowDefinitionRequest,
    ActivityDefinitionRequest,
    ParameterDefinition,
)
from xians.models.v1 import AgentRequest, AgentResponse

@activity.defn
async def execute_conversational_agent(request: AgentRequest) -> AgentResponse:
    """Conversational agent with server integration."""
    # Your agent logic here
    message = request.message if isinstance(request.message, str) else str(request.message)
    result = f"Response to: {message}"
    
    return AgentResponse(
        text=result,
        usage={"prompt_tokens": 50, "completion_tokens": 30},
        model="gpt-4",
    )

async def main():
    options = XiansOptions(
        server_url="https://api.xians.ai",
        api_key="your-api-key",
        temporal=TemporalConfig(host="localhost", port=7233),
    )
    
    platform = await XiansPlatform.initialize(options)
    
    # Register agent and workflow
    agent = platform.agents.register(name="ConversationalAgent")
    agent.define_conversation_workflow(
        name="Conversation",
        workers=1,
        activity_func=execute_conversational_agent,
    )
    
    # Upload flow definition to server
    param = ParameterDefinition(name="message", type="string")
    activity_def = ActivityDefinitionRequest(activity_name="chat")
    flow = FlowDefinitionRequest(
        agent="ConversationalAgent",
        workflow_type="Conversational",
        activity_definitions=[activity_def],
        parameter_definitions=[param],
    )
    
    try:
        await platform.server_client.upload_flow_definition(flow)
        print("✓ Flow definition uploaded")
    except Exception as e:
        print(f"✗ Upload failed: {e}")
    
    # Start workers
    await platform.run_all()

async def client_example():
    options = XiansOptions(
        server_url="https://api.xians.ai",
        api_key="your-api-key",
        temporal=TemporalConfig(host="localhost", port=7233),
    )
    
    platform = await XiansPlatform.initialize(options)
    await platform.connect_temporal()
    client = platform.client()
    
    # Send chat message
    request = ChatOrDataRequest(
        participant_id="user_123",
        text="Hello!",
    )
    
    response = await platform.server_client.send_outbound_chat(request)
    print(f"Chat sent: {response}")
    
    # Report usage
    usage = UsageReportRequest(
        prompt_tokens=50,
        completion_tokens=30,
        total_tokens=80,
        message_count=1,
    )
    
    response = await platform.server_client.report_usage(usage)
    print(f"Usage reported: {response}")
    
    await platform.shutdown()

if __name__ == "__main__":
    # Run server
    asyncio.run(main())
    
    # Or run client in another process
    # asyncio.run(client_example())
```

---

## Xians Server Integration API

The Xians Python SDK provides typed, production-ready methods for interacting with the Xians Server REST API. All methods use Pydantic v2 models with strict validation and camelCase JSON serialization.

### Overview

The Xians Server API provides five categories of operations:

1. **Definitions** - Upload and manage agent/workflow definitions
2. **Conversation Outbound** - Send messages, data, webhooks, and handoffs to participants
3. **Usage Reporting** - Report token consumption and usage metrics
4. **Knowledge** - Manage knowledge bases
5. **Documents** - Store, retrieve, and query documents

### Prerequisites

Before using these APIs, initialize the platform:

```python
from xians.interfaces.v1.xians_client import XiansServerClient
from xians.models.v1.configs import XiansServerConfig

config = XiansServerConfig(
    server_url="https://api.xians.ai",
    auth_mode="bearer_cert",
    bearer_cert_base64="your-bearer-token",
)

client = XiansServerClient(config)
```

### A) Definitions Upload

Upload agent and workflow definitions to the Xians Server.

#### `client.upload_flow_definition(definition: FlowDefinitionRequest) -> dict`

Upload a flow definition to `POST /api/agent/definitions`.

**Example:**
```python
from xians.models.v1.server_contracts import (
    FlowDefinitionRequest,
    ActivityDefinitionRequest,
    ParameterDefinition,
)

# Define parameters
param = ParameterDefinition(
    name="input_message",
    type="string",
)

# Define activities
activity = ActivityDefinitionRequest(
    activity_name="process_message",
    knowledge_ids=["kb_001", "kb_002"],
    parameter_definitions=[param],
)

# Create and upload flow definition
flow = FlowDefinitionRequest(
    agent="MyAgent",
    workflow_type="Conversational",
    name="Main Workflow",
    activity_definitions=[activity],
    parameter_definitions=[param],
    system_scoped=False,
)

response = await client.upload_flow_definition(flow)
print(f"Upload response: {response}")
```

**Validation:**
- `agent` and `workflowType` must be non-empty strings
- `activityDefinitions` must have at least 1 entry
- `parameterDefinitions` must have at least 1 entry
- Each activity must include `knowledgeIds` and `parameterDefinitions` keys (can be empty arrays)

**Errors:**
- `XiansServerError(status_code=400)` - Payload validation failed; check required fields

---

### B) Conversation Outbound APIs

Send messages and data to participants in conversations.

#### `client.send_outbound_chat(request: ChatOrDataRequest) -> dict`

Send chat message to `POST /api/agent/conversation/outbound/chat`.

**Example:**
```python
from xians.models.v1.server_contracts import ChatOrDataRequest

request = ChatOrDataRequest(
    participant_id="user_123",
    text="Hello! How can I help?",
    workflow_id="wf_456",
)

response = await client.send_outbound_chat(request)
```

#### `client.send_outbound_data(request: ChatOrDataRequest) -> dict`

Send structured data to `POST /api/agent/conversation/outbound/data`.

**Example:**
```python
request = ChatOrDataRequest(
    participant_id="user_123",
    data={
        "action": "update_status",
        "status": "completed",
        "metadata": {"timestamp": "2026-01-07T10:00:00Z"}
    },
)

response = await client.send_outbound_data(request)
```

#### `client.send_outbound_webhook(request: ChatOrDataRequest) -> dict`

Send webhook to `POST /api/agent/conversation/outbound/webhook`.

**Example:**
```python
request = ChatOrDataRequest(
    participant_id="user_123",
    data={"event": "conversation_started", "timestamp": 1704633600},
)

response = await client.send_outbound_webhook(request)
```

#### `client.send_handoff(request: HandoffRequest) -> dict`

Send handoff request to `POST /api/agent/conversation/outbound/handoff`.

**Example:**
```python
from xians.models.v1.server_contracts import HandoffRequest

request = HandoffRequest(
    participant_id="user_123",
    target="human_agent",
    reason="User requested escalation",
    text="Transferring to human support team",
)

response = await client.send_handoff(request)
```

**Validation:**
- `participant_id` must be non-empty string
- `target` in handoff request indicates handoff destination
- Other fields are optional

---

### C) Usage Reporting

Report token consumption and usage metrics to the Xians Server.

#### `client.report_usage(request: UsageReportRequest) -> dict`

Report usage to `POST /api/agent/usage/report`.

**Example:**
```python
from xians.models.v1.server_contracts import UsageReportRequest

request = UsageReportRequest(
    model="gpt-4",
    workflow_id="wf_123",
    request_id="req_456",
    source="openai",
    prompt_tokens=150,
    completion_tokens=75,
    total_tokens=225,
    message_count=2,
    response_time_ms=1200,
    metadata={"region": "us-east-1", "version": "1.0"},
)

response = await client.report_usage(request)
```

**Validation:**
- All token counts (`promptTokens`, `completionTokens`, `totalTokens`, `messageCount`) must be integers >= 0
- At least one counter should be > 0 (SDK logs warning if all are 0)
- All other fields are optional

---

### D) Knowledge Management

Manage knowledge bases for agents.

#### `client.get_latest_knowledge(name: str, agent: str) -> dict`

Get latest knowledge by name and agent. (`GET /api/agent/knowledge/latest`)

**Example:**
```python
kb = await client.get_latest_knowledge(
    name="product_faq",
    agent="MyAgent",
)
```

#### `client.list_knowledge(agent: str) -> dict`

List all knowledge for an agent. (`GET /api/agent/knowledge/list`)

**Example:**
```python
all_kb = await client.list_knowledge(agent="MyAgent")
```

#### `client.create_knowledge(name: str, agent: str, type: str, content: str) -> dict`

Create new knowledge. (`POST /api/agent/knowledge`)

**Example:**
```python
kb = await client.create_knowledge(
    name="product_faq",
    agent="MyAgent",
    type="document",
    content="Q: What is your product? A: It is a Temporal-first agent runtime...",
)
```

#### `client.delete_knowledge(name: str, agent: str) -> dict`

Delete knowledge by name and agent. (`DELETE /api/agent/knowledge`)

**Example:**
```python
response = await client.delete_knowledge(
    name="product_faq",
    agent="MyAgent",
)
```

---

### E) Document Management

Store, retrieve, and query documents.

#### `client.save_document(document: dict, options: dict | None = None) -> dict`

Save a document. (`POST /api/agent/documents/save`)

**Example:**
```python
doc = {
    "title": "User Profile",
    "user_id": "user_123",
    "email": "user@example.com",
}

response = await client.save_document(
    document=doc,
    options={"index": True},
)
```

#### `client.get_document(id: str) -> dict`

Get document by ID. (`POST /api/agent/documents/get`)

**Example:**
```python
doc = await client.get_document(id="doc_789")
```

#### `client.get_document_by_key(type: str, key: str) -> dict`

Get document by type and key. (`POST /api/agent/documents/get-by-key`)

**Example:**
```python
doc = await client.get_document_by_key(
    type="user_profile",
    key="user_123",
)
```

#### `client.query_documents(query: dict, content_type: str | None = None) -> dict`

Query documents. (`POST /api/agent/documents/query`)

**Example:**
```python
results = await client.query_documents(
    query={"status": "active", "created_after": "2026-01-01"},
    content_type="application/json",
)
```

#### `client.update_document(document: dict, options: dict | None = None) -> dict`

Update a document. (`POST /api/agent/documents/update`)

**Example:**
```python
response = await client.update_document(
    document={"id": "doc_789", "title": "Updated Title"},
    options={"merge": True},
)
```

#### `client.delete_document(id: str) -> dict`

Delete document by ID. (`POST /api/agent/documents/delete`)

**Example:**
```python
response = await client.delete_document(id="doc_789")
```

#### `client.delete_many_documents(ids: list[str]) -> dict`

Delete multiple documents. (`POST /api/agent/documents/delete-many`)

**Example:**
```python
response = await client.delete_many_documents(
    ids=["doc_789", "doc_790", "doc_791"]
)
```

#### `client.document_exists(id: str) -> dict`

Check if document exists. (`POST /api/agent/documents/exists`)

**Example:**
```python
result = await client.document_exists(id="doc_789")
# Returns: {"exists": true} or {"exists": false}
```

---

### Error Handling

All Xians Server API calls raise `XiansServerError` on failure:

```python
from xians.exceptions.v1.errors import XiansServerError

try:
    response = await client.upload_flow_definition(flow)
except XiansServerError as e:
    print(f"Status Code: {e.status_code}")
    print(f"Method: {e.method}")
    print(f"URL: {e.url}")
    print(f"Response: {e.response_body}")
```

**Common Status Codes:**
- `400` - Bad Request (payload validation failed)
- `401` - Unauthorized (invalid/expired API key)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error

---

### Complete Example: End-to-End Workflow

```python
import asyncio
from xians.interfaces.v1.xians_client import XiansServerClient
from xians.models.v1.configs import XiansServerConfig
from xians.models.v1.server_contracts import (
    FlowDefinitionRequest,
    ActivityDefinitionRequest,
    ParameterDefinition,
    ChatOrDataRequest,
    UsageReportRequest,
)

async def main():
    # Initialize client
    config = XiansServerConfig(
        server_url="https://api.xians.ai",
        auth_mode="bearer_cert",
        bearer_cert_base64="your-token",
    )
    client = XiansServerClient(config)
    
    try:
        # 1. Define and upload workflow
        param = ParameterDefinition(name="message", type="string")
        activity = ActivityDefinitionRequest(
            activity_name="chat",
            knowledge_ids=["kb_001"],
        )
        flow = FlowDefinitionRequest(
            agent="MyBot",
            workflow_type="Conversational",
            activity_definitions=[activity],
            parameter_definitions=[param],
        )
        await client.upload_flow_definition(flow)
        print("✓ Workflow uploaded")
        
        # 2. Send chat message
        chat_req = ChatOrDataRequest(
            participant_id="user_123",
            text="Hello bot!",
        )
        await client.send_outbound_chat(chat_req)
        print("✓ Chat sent")
        
        # 3. Report usage
        usage = UsageReportRequest(
            prompt_tokens=50,
            completion_tokens=100,
            total_tokens=150,
            message_count=1,
        )
        await client.report_usage(usage)
        print("✓ Usage reported")
        
        # 4. Save conversation to documents
        doc = {
            "conversation_id": "conv_123",
            "user_id": "user_123",
            "messages": [{"role": "user", "content": "Hello bot!"}],
        }
        await client.save_document(document=doc)
        print("✓ Document saved")
        
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
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
