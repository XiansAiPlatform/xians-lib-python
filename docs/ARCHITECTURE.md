# Xians Python SDK - Architecture

## Overview

The Xians Python SDK is designed as a **Temporal-first agent execution substrate** that is completely **framework-agnostic**. This document explains the architecture, design decisions, and internal workings.

---

## Design Principles

### 1. Temporal-First Architecture

The SDK is built around Temporal as the execution substrate:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Space                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent Implementation (Any Framework)                   │ │
│  │  - LangChain                                           │ │
│  │  - Custom code                                          │ │
│  │  - Semantic Kernel                                      │ │
│  │  - Or anything else                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Activity: execute_agent_activity(request) -> response │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    SDK Layer (This Library)                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Workflows (SDK-Owned, Deterministic)                  │ │
│  │  - InvokeAgentWorkflow                                 │ │
│  │  - ConversationWorkflow                                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Worker Management                                      │ │
│  │  - WorkerHost                                          │ │
│  │  - WorkerRegistry                                       │ │
│  │  - Task queue routing                                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Temporal Server                            │
│  - Workflow orchestration                                    │
│  - State management                                          │
│  - Retries & timeouts                                        │
│  - Event sourcing                                            │
└─────────────────────────────────────────────────────────────┘
```

### 2. Framework-Agnostic Design

**Core Principle**: The SDK does NOT dictate how you build your agent.

- ✅ **Activities are black boxes** - SDK calls them, doesn't inspect them
- ✅ **AgentRequest/AgentResponse** - Simple, universal interfaces
- ✅ **No framework dependencies** - No LangChain, no Semantic Kernel, nothing
- ❌ **No LLM adapter** - Users integrate their own LLM providers

### 3. Separation of Concerns

```
XiansPlatform (Facade)
    ↓
    ├─→ AgentRegistry (Agent management)
    │       ├─→ AgentRegistration
    │       └─→ AgentDefinition
    │
    ├─→ WorkerHost (Temporal worker management)
    │       ├─→ WorkerRegistry
    │       └─→ Worker instances
    │
    ├─→ XiansServerClient (Optional: Server integration)
    │       ├─→ Definition upload
    │       ├─→ Settings discovery
    │       └─→ Conversation/Knowledge APIs
    │
    └─→ AgentClient (Workflow invocation)
            ├─→ invoke()
            ├─→ start_conversation()
            ├─→ send_update()
            └─→ query()
```

---

## Component Architecture

### 1. Platform Layer (`interfaces/v1/platform.py`)

**XiansPlatform** is the main facade that orchestrates all components.

**Responsibilities:**
- Initialize SDK components
- Manage agent registrations
- Configure workers
- Connect to Temporal
- Upload definitions to Xians Server

**Key Methods:**
```python
# Initialization
platform = await XiansPlatform.initialize(options)

# Agent registration
agent = platform.agents.register(name="MyAgent")

# Workflow definition
agent.define_invoke_workflow(activity_func=my_activity)

# Worker execution
await platform.run_all()  # Start workers and block

# Client access
client = platform.client()  # Get client for invoking workflows
```

### 2. Workflow Layer (`temporal_workflows/v1/`)

**Workflows are SDK-owned** and must remain deterministic.

#### InvokeAgentWorkflow

Purpose: One-shot agent execution (request-response).

```python
@workflow.defn
class InvokeAgentWorkflow:
    async def run(self, request: AgentRequest) -> AgentResponse:
        # 1. Get activity name from memo
        activity_name = workflow.memo_value("activity_name", default="execute_agent_activity")
        
        # 2. Execute activity with retry policy
        response = await workflow.execute_activity(
            activity_name,
            request,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(...),
        )
        
        # 3. Return response
        return response
```

**Key Features:**
- Deterministic execution
- Configurable timeouts
- Automatic retries
- Error handling

#### ConversationWorkflow

Purpose: Long-running conversational sessions.

```python
@workflow.defn
class ConversationWorkflow:
    def __init__(self):
        self._messages = []
        self._session_metadata = {}
    
    async def run(self, agent_key: str, conversation_id: str):
        # Run indefinitely until cancelled
        await workflow.wait_condition(lambda: False)
    
    @workflow.signal
    async def inbound_message(self, message: str, metadata: dict):
        # Fire-and-forget message handling
        self._messages.append({"message": message, ...})
    
    @workflow.update
    async def request_response(self, message: str, metadata: dict) -> AgentResponse:
        # Request-response message handling
        request = AgentRequest(...)
        return await workflow.execute_activity(self._activity_name, request, ...)
    
    @workflow.query
    def get_session_state(self) -> dict:
        # Query current state
        return {"message_count": len(self._messages), ...}
```

**Key Features:**
- Long-running (indefinite)
- Signals for fire-and-forget
- Updates for request-response
- Queries for state inspection
- Session state management

### 3. Worker Management (`temporal_workflows/v1/worker_runner.py`)

**WorkerHost** manages the Temporal worker lifecycle.

```python
class WorkerHost:
    async def connect(self) -> None:
        """Connect to Temporal server."""
        self.client = await Client.connect(
            f"{self.config.host}:{self.config.port}",
            namespace=self.config.namespace,
            tls=tls_config,
        )
    
    def register_workflow(self, workflow_class: type) -> None:
        """Register a workflow class."""
        self._workflows.append(workflow_class)
    
    def register_activity(self, activity_func: Callable) -> None:
        """Register an activity function."""
        self._activities.append(activity_func)
    
    async def start_worker(self, task_queue: str, ...) -> Worker:
        """Start a worker on a task queue."""
        worker = Worker(
            self.client,
            task_queue=task_queue,
            workflows=self._workflows,
            activities=self._activities,
            max_concurrent_activities=10,
        )
        asyncio.create_task(worker.run())
        return worker
```

**WorkerRegistry** tracks workflow/activity registrations.

```python
class WorkerRegistry:
    def register(
        self,
        agent_key: str,
        workflow_name: str,
        workflow_class: type,
        activity_func: Callable,
        tenant_id: str | None = None,
        system_scoped: bool = False,
        workers: int = 1,
    ) -> str:
        """Register a workflow + activity combination."""
        task_queue = build_task_queue_name(
            agent_key, workflow_name, tenant_id, system_scoped
        )
        self._registrations[task_queue] = {
            "workflow_class": workflow_class,
            "activity_func": activity_func,
            "workers": workers,
        }
        return task_queue
```

### 4. Task Queue Naming

**Critical Design Decision**: Task queues must be deterministic and predictable.

```python
def build_task_queue_name(
    agent_key: str,
    workflow_name: str,
    tenant_id: str | None = None,
    system_scoped: bool = False,
) -> str:
    """
    Build task queue name: xians-{tenant}-{scope}-{agent}-{workflow}
    
    Examples:
        xians-default-user-MyAgent-InvokeAgent
        xians-tenant123-system-SystemAgent-Conversation
    """
    scope = "system" if system_scoped else "user"
    tenant_part = tenant_id if tenant_id else "default"
    return f"xians-{tenant_part}-{scope}-{agent_key}-{workflow_name}"
```

**Why Deterministic Naming?**
1. **Routing**: Same agent + workflow + tenant always routes to same queue
2. **Xians Server**: Can reliably route requests to correct workers
3. **Multi-tenancy**: Isolated queues per tenant
4. **Scalability**: Horizontal scaling per queue

### 5. Xians Server Integration (`interfaces/v1/xians_client.py`)

**XiansServerClient** provides HTTP client for Xians Server APIs.

**Key Features:**
- **Idempotent definition uploads** using content hashing
- **Local cache** of uploaded hashes
- **Retry logic** for transient failures
- **Optional integration** - SDK works without server

```python
class XiansServerClient:
    async def fetch_temporal_settings(self) -> dict:
        """Fetch Temporal connection info from server."""
        response = await self._client.get("/api/agent/settings/flowserver")
        return response.json()
    
    async def upload_agent_definition(self, definition: AgentDefinition) -> str:
        """Upload agent definition (idempotent)."""
        # Compute content hash
        content = definition.model_dump_json(exclude={"hash", "agent_key"})
        definition_hash = compute_hash(content)
        
        # Check cache
        if self._uploaded_hashes.get(f"agent:{definition.name}") == definition_hash:
            return definition.agent_key  # Already uploaded
        
        # Upload to server
        response = await self._client.post("/api/agent/definitions", json=definition.model_dump())
        
        # Cache hash
        self._uploaded_hashes[f"agent:{definition.name}"] = definition_hash
        self._save_cache()
        
        return response.json()["agent_key"]
```

### 6. Client Layer (`interfaces/v1/agent_client.py`)

**AgentClient** provides workflow invocation APIs.

```python
class AgentClient:
    async def invoke(self, workflow_id: str, task_queue: str, request: AgentRequest) -> AgentResponse:
        """Invoke one-shot agent execution."""
        handle = await self.client.start_workflow(
            "InvokeAgentWorkflow",
            request,
            id=workflow_id,
            task_queue=task_queue,
        )
        return await handle.result()
    
    async def start_conversation(self, ...) -> WorkflowHandle:
        """Start long-running conversation."""
        return await self.client.start_workflow(
            "ConversationWorkflow",
            args=[agent_key, conversation_id],
            id=workflow_id,
            task_queue=task_queue,
        )
    
    async def send_update(self, workflow_id: str, update_name: str, *args) -> Any:
        """Send update to workflow (request-response)."""
        handle = self.client.get_workflow_handle(workflow_id)
        return await handle.execute_update(update_name, *args)
```

---

## Data Flow

### Invoke Workflow (One-Shot)

```
1. Client → invoke(workflow_id, task_queue, request)
              ↓
2. Temporal Server → Route to worker on task_queue
              ↓
3. Worker → InvokeAgentWorkflow.run(request)
              ↓
4. Workflow → execute_activity("execute_agent_activity", request)
              ↓
5. Activity → User's agent code (ANY framework)
              ↓
6. Activity → Return AgentResponse
              ↓
7. Workflow → Return AgentResponse
              ↓
8. Client ← AgentResponse
```

### Conversation Workflow (Long-Running)

```
1. Client → start_conversation(workflow_id, ...)
              ↓
2. Worker → ConversationWorkflow.run(agent_key, conversation_id)
              ↓ (workflow runs indefinitely)
3. Client → send_update("request_response", message)
              ↓
4. Workflow.request_response() → execute_activity(request)
              ↓
5. Activity → User's agent code
              ↓
6. Activity → Return AgentResponse
              ↓
7. Workflow → Return AgentResponse
              ↓
8. Client ← AgentResponse

9. Client → query("get_session_state")
              ↓
10. Workflow.get_session_state() → Return state
              ↓
11. Client ← State dict
```

---

## Key Design Decisions

### 1. Why Temporal?

- ✅ **Durability**: Workflows survive failures
- ✅ **Retries**: Automatic retry with backoff
- ✅ **Long-running**: Supports workflows that run for days/weeks
- ✅ **State management**: Built-in state persistence
- ✅ **Event sourcing**: Complete execution history
- ✅ **Scalability**: Horizontal scaling of workers

### 2. Why Activities for Agent Logic?

- ✅ **Non-determinism**: Activities can do I/O, call APIs, etc.
- ✅ **Retries**: Failed activities automatically retry
- ✅ **Timeouts**: Configurable timeouts per activity
- ✅ **Framework-agnostic**: Activity is just a function

### 3. Why Not Include LLM Adapters?

- ✅ **Framework-agnostic**: Users choose their own frameworks
- ✅ **No vendor lock-in**: Not tied to specific LLM providers
- ✅ **Flexibility**: Users can use ANY agent implementation
- ✅ **Maintainability**: SDK doesn't need to keep up with every LLM API change

### 4. Why Xians Server is Optional?

- ✅ **Standalone**: Core functionality works without server
- ✅ **Flexibility**: Users can deploy without Xians Server
- ✅ **Value-add**: Server provides additional features (settings, registry, APIs)

---

## Performance Considerations

### Worker Scaling

```python
# Scale workers per workflow
agent.define_invoke_workflow(
    name="HighThroughput",
    workers=10,  # 10 workers processing this queue
)
```

### Activity Concurrency

```python
# Configure concurrent activities per worker
await worker_host.start_worker(
    task_queue="my-queue",
    max_concurrent_activities=100,  # Process 100 activities in parallel
)
```

### Task Queue Partitioning

```python
# Partition by tenant for isolation
for tenant in tenants:
    task_queue = build_task_queue_name(
        agent_key="MyAgent",
        workflow_name="Invoke",
        tenant_id=tenant.id,  # Separate queue per tenant
    )
```

---

## Security Considerations

### 1. API Key Management

```python
# Use environment variables
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    xians_api_key: str
    openai_api_key: str
    
    class Config:
        env_file = ".env"
```

### 2. TLS for Temporal

```python
TemporalConfig(
    host="temporal.example.com",
    port=7233,
    tls_enabled=True,
    tls_cert_path="/path/to/cert.pem",
)
```

### 3. Multi-Tenancy Isolation

- Task queues isolated by tenant
- Separate workers per tenant (optional)
- Tenant ID in all requests

---

## Future Enhancements

1. **Custom Workflow Support**: Allow users to define their own workflows
2. **Batch Processing**: Support for batch agent invocations
3. **Streaming Responses**: Support for streaming LLM responses
4. **Metrics & Observability**: Built-in metrics collection
5. **Circuit Breakers**: Fail-fast for unhealthy dependencies

---

## References

- [Temporal Documentation](https://docs.temporal.io/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [HTTPX Documentation](https://www.python-httpx.org/)

