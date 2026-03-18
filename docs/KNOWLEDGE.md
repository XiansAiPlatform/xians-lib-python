# Knowledge

## Give Your Agents Domain Expertise

LLMs are smart, but they don't know **your** business. Knowledge bases solve this
through **Retrieval-Augmented Generation (RAG)** — letting agents retrieve your
content and ground their answers in your truth.

This document covers the Python SDK implementation of the Knowledge feature,
mirroring the C# `Xians.Lib.Agents.Knowledge` module.

---

## What is Agent Knowledge?

Every agent has its own **private knowledge base** — a key-value store for
information your agent needs to retrieve at runtime:

- **System instructions** that customize agent behavior
- **Product catalogs** for a sales agent
- **Company policies** for a support agent
- **User preferences** for a personalization agent
- **Workflow instructions** for complex processes

Knowledge is **automatically scoped** to each agent. Agent A cannot access
Agent B's knowledge — perfect for multi-tenant applications.

---

## Quick Start

```python
from xians.agents.core import XiansContext

async def my_chat_handler(context) -> None:
    agent = XiansContext.CurrentAgent

    # Get specific knowledge by name
    knowledge = await agent.knowledge.get_async("welcome-message")
    if knowledge:
        print(f"Content: {knowledge.content}")
        print(f"Type: {knowledge.type}")

    # List all knowledge
    all_knowledge = await agent.knowledge.list_async()
    for item in all_knowledge:
        print(f"{item.name}: {item.content[:50]}...")

    # Create or update knowledge
    await agent.knowledge.update_async(
        "greeting",
        "Hello! How can I help you today?",
        type="text",
    )

    # Delete knowledge
    await agent.knowledge.delete_async("old-instructions")
```

---

## API Reference

### `KnowledgeCollection`

The `KnowledgeCollection` is the public facade exposed as `agent.knowledge`.
It is accessible via:

```python
agent = XiansContext.CurrentAgent
agent.knowledge  # KnowledgeCollection instance
```

#### `get_async(knowledge_name: str) -> Optional[KnowledgeItem]`

Retrieve knowledge by name. Uses **progressive fallback** on the server side:

1. Instance-scoped (tenant/agent/activation)
2. Tenant-scoped (tenant/agent)
3. System-scoped (system/agent)

Returns the first match found, or `None` if not found.

```python
knowledge = await agent.knowledge.get_async("system-instructions")
if knowledge:
    instructions = knowledge.content
```

#### `get_system_async(knowledge_name: str) -> Optional[KnowledgeItem]`

Retrieve system-scoped knowledge directly (bypasses tenant lookup).

```python
default_instructions = await agent.knowledge.get_system_async("system-instructions")
```

#### `list_async() -> list[KnowledgeItem]`

List all knowledge entries for this agent.

```python
items = await agent.knowledge.list_async()
for item in items:
    print(f"  {item.name} [{item.type}]: {item.content[:80]}")
```

#### `update_async(knowledge_name, content, type=None, system_scoped=None, description=None, visible=True) -> bool`

Create or update a knowledge entry. Returns `True` on success.

```python
success = await agent.knowledge.update_async(
    "api-config",
    '{"endpoint": "https://api.example.com", "timeout": 30}',
    type="json",
    description="External API configuration",
)
```

#### `delete_async(knowledge_name: str) -> bool`

Delete a knowledge entry. Returns `True` on success.

```python
deleted = await agent.knowledge.delete_async("old-instructions")
```

#### `display_summary_async() -> None`

Log a formatted summary of all locally cached knowledge entries.

```python
await agent.knowledge.display_summary_async()
```

---

### `KnowledgeItem`

The data model for a single knowledge entry.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Knowledge name (key) |
| `content` | `str` | Knowledge content body |
| `type` | `Optional[str]` | Content type: `text`, `markdown`, `json`, `xml`, `yaml` |
| `id` | `Optional[str]` | Server-assigned identifier |
| `version` | `Optional[str]` | Version string |
| `agent` | `Optional[str]` | Owning agent name |
| `tenant_id` | `Optional[str]` | Tenant scope |
| `system_scoped` | `bool` | `True` = shared across all tenants |
| `description` | `Optional[str]` | Human-readable description |
| `visible` | `bool` | Whether visible in listings |

---

## Progressive Knowledge Retrieval

The Xians platform uses a **progressive fallback mechanism** when retrieving
knowledge. When you call `get_async("knowledge-name")`, the server checks:

1. **Instance-Scoped** (`tenant/agent/activation`) — Most specific to this agent run
2. **Tenant-Scoped** (`tenant/agent`) — Specific to this tenant's agent
3. **System-Scoped** (`system/agent`) — Template/default shared across all tenants

The server returns the **first match found**.

### Automatic Tenant Replica

When `get_async` is called on a tenant-scoped agent and the server returns
system-scoped knowledge, the SDK automatically creates a tenant-scoped copy.
This mirrors C# `KnowledgeCollection.GetAsync` behavior, enabling per-tenant
customization from system defaults.

### Benefits

- **Defaults for all** — System-scoped knowledge provides baseline behavior
- **Tenant customization** — Each tenant can override with their own rules
- **Instance personalization** — Individual agent runs can be further customized
- **Efficient storage** — Only store overrides, not duplicate defaults

---

## Caching

Knowledge reads from the server are **cached in-memory** with a configurable TTL
(default: 10 minutes). The cache is automatically invalidated when you call
`update_async` or `delete_async`.

---

## Agent Isolation

Each agent's knowledge is **completely isolated**:

```python
sales_agent = XiansContext.get_agent("SalesAgent")
support_agent = XiansContext.get_agent("SupportAgent")

# Sales agent retrieves its knowledge
pricing = await sales_agent.knowledge.get_async("pricing")

# Support agent cannot see Sales agent's knowledge
leaked = await support_agent.knowledge.get_async("pricing")
# Returns None — agents are isolated by tenant and name
```

---

## Knowledge in Workflows

Knowledge retrieval works seamlessly inside both **built-in** and **custom**
workflows. `XiansContext.CurrentAgent` resolves from Temporal context automatically.

### Built-in Workflow (Chat Handler)

```python
from xians.agents.core import XiansContext
from xians.agents.messaging import UserMessageContext

async def my_chat_handler(context: UserMessageContext) -> None:
    agent = XiansContext.CurrentAgent

    instructions = await agent.knowledge.get_async("system-instructions")
    system_prompt = instructions.content if instructions else "You are a helpful assistant."

    # Use system_prompt with your LLM...
    await context.reply_async("Response based on knowledge")
```

### Custom Workflow Activity

```python
from temporalio import activity
from xians.agents.core import XiansContext

@activity.defn(name="ProcessWithKnowledge")
async def process_with_knowledge(query: str) -> str:
    agent = XiansContext.CurrentAgent

    config = await agent.knowledge.get_async("api-config")
    if config and config.type == "json":
        import json
        settings = json.loads(config.content)
        # Use settings...

    return f"Processed: {query}"
```

---

## Common Usage Patterns

### Retrieving System Instructions

```python
async def my_chat_handler(context: UserMessageContext) -> None:
    agent = XiansContext.CurrentAgent
    system_instructions = await agent.knowledge.get_async("system-instructions")

    messages = [
        {"role": "system", "content": system_instructions.content if system_instructions else "Default instructions"},
        {"role": "user", "content": context.message.text},
    ]

    response = await llm.get_completion(messages)
    await context.reply_async(response)
```

### Loading JSON Configuration

```python
import json

config_knowledge = await agent.knowledge.get_async("api-config")
if config_knowledge and config_knowledge.type == "json":
    settings = json.loads(config_knowledge.content)
    api_url = settings["endpoint"]
    timeout = settings["timeout"]
```

### Uploading Knowledge from Files at Startup

The **primary pattern** (matching C# `UploadEmbeddedResourceAsync`) is to upload
local knowledge files to the platform at agent startup. This ensures knowledge
is available on the server for all workers and instances:

```python
# In your main.py, after registering the agent:
knowledge_files = [
    {
        "resource_path": "knowledge/System Instructions.md",
        "knowledge_name": "system-instructions",
        "knowledge_type": "markdown",
        "description": "Main system prompt for the agent",
        "visible": False,
    },
    {
        "resource_path": "knowledge/Ideal Customer Profile.md",
        "knowledge_name": "ideal-customer-profile",
        "knowledge_type": "markdown",
        "description": "ICP rules for lead qualification",
        "visible": True,
    },
]

for kf in knowledge_files:
    try:
        await agent.knowledge.upload_from_file(**kf)
    except Exception as ex:
        logger.warning("Failed to upload knowledge '%s': %s", kf["knowledge_name"], ex)
```

This is the exact equivalent of the C# lead-discovery-agent pattern:

```csharp
// C# equivalent
await agent.Knowledge.UploadEmbeddedResourceAsync(
    resourcePath: "knowledge/System Instructions.md",
    knowledgeName: "system-instructions",
    knowledgeType: "markdown",
    description: "Main system prompt");
```

---

## Uploading Knowledge — API Reference

#### `upload_from_file(resource_path, knowledge_name=None, knowledge_type=None, ...) -> bool`

Read a local file and upload it as a knowledge entry. Mirrors C# `UploadEmbeddedResourceAsync`.

```python
await agent.knowledge.upload_from_file(
    "knowledge/System Instructions.md",
    knowledge_name="system-instructions",
    knowledge_type="markdown",
    description="System prompt for the agent",
    visible=False,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resource_path` | `str \| Path` | required | Path to the file (relative or absolute) |
| `knowledge_name` | `str \| None` | filename stem | Knowledge key (e.g. `"system-instructions"`) |
| `knowledge_type` | `str \| None` | from extension | Content type (`markdown`, `text`, `json`, etc.) |
| `system_scoped` | `bool \| None` | agent's scope | Override scope |
| `description` | `str \| None` | `None` | Human-readable description |
| `visible` | `bool` | `True` | Whether visible in listings |

If `knowledge_name` is omitted, the filename stem is used (e.g. `"System Instructions.md"` → `"System Instructions"`).
If `knowledge_type` is omitted, it is inferred from the file extension.

#### `upload_text(knowledge_name, content, knowledge_type=None, ...) -> bool`

Upload raw text as a knowledge entry. Mirrors C# `UploadTextResourceAsync`.

```python
await agent.knowledge.upload_text(
    "greeting",
    "Hello! How can I help you today?",
    knowledge_type="text",
)
```

---

## Knowledge File Layout

Knowledge files live alongside your agent code, typically in a `knowledge/` folder:

```
my-agent/
├── main.py
├── .env
└── knowledge/
    ├── System Instructions.md
    ├── Ideal Customer Profile.md
    ├── Harvesting Sources.json
    └── Product Offerings Extract Instructions.md
```

This mirrors the C# pattern where knowledge files are placed in a `knowledge/`
folder and compiled as embedded resources via `.csproj`. In Python, the files
are read from disk at startup and uploaded to the server.

### Supported File Extensions

| Extension | Inferred `type` |
|-----------|-----------------|
| `.md` | `markdown` |
| `.txt` | `text` |
| `.json` | `json` |
| `.xml` | `xml` |
| `.yaml` / `.yml` | `yaml` |

---

## Local Mode (Development / Testing)

When `XiansOptions.local_mode = True`, the SDK uses `LocalKnowledgeProvider`
instead of making HTTP calls to the server. This is useful for unit tests
and local development without a running Xians Server.

### How It Works

- **In-memory store**: `update_async` / `delete_async` operate on an in-memory dict.
- **File fallback**: `get_async` falls back to loading from a local knowledge folder
  if the item is not found in memory.

### Setting Up the Knowledge Folder

The `LocalKnowledgeProvider` resolves the knowledge folder from:

1. **`LOCAL_KNOWLEDGE_FOLDER` environment variable** (matches C# .env convention).
2. Or an explicit `knowledge_dir` parameter passed to the factory.

In your `.env`:

```env
LOCAL_KNOWLEDGE_FOLDER=./knowledge
```

### File Naming Convention

Files must be named `{KnowledgeName}.{ext}`. The provider searches:

1. `{knowledge_dir}/{KnowledgeName}.{ext}` — direct match
2. `{knowledge_dir}/{AgentName}/{KnowledgeName}.{ext}` — agent subfolder
3. Normalized name fallback: `system-instructions` matches `system-instructions.md`
4. Suffix fallback: any file ending with `.{normalized-name}.{ext}` (mirrors C#
   `TryLoadResourceBySuffix`)

Extensions searched: `.md`, `.txt`, `.json` (matching C#).

### Example

```
knowledge/
├── system-instructions.md
├── api-config.json
└── greeting.txt
```

```python
# In code (local_mode=True)
agent = XiansContext.CurrentAgent
instructions = await agent.knowledge.get_async("system-instructions")
# Reads from: knowledge/system-instructions.md
```

### Local Mode vs Server Mode

| | Server Mode (default) | Local Mode (`local_mode=True`) |
|---|---|---|
| **Provider** | `ServerKnowledgeProvider` | `LocalKnowledgeProvider` |
| **Data source** | Xians Server HTTP API | In-memory + file fallback |
| **Knowledge folder** | N/A | `LOCAL_KNOWLEDGE_FOLDER` env var |
| **upload_from_file** | Reads file, uploads to server | Reads file, stores in memory |

> In production (server mode), always use `upload_from_file` at startup to push
> knowledge to the server. The local file fallback only applies in `local_mode`.

### Full Working Example

See [`examples/web-search-agent/`](../examples/web-search-agent/) for a complete
example:

```
examples/web-search-agent/
├── main.py                             # Uploads knowledge at startup
├── web_search_sub_agent.py             # Fetches system-instructions at runtime
├── .env
└── knowledge/
    └── system-instructions.md          # System prompt
```

**`main.py` (key lines):**

```python
# Upload knowledge to the server at startup (mirrors C# UploadEmbeddedResourceAsync)
await agent.knowledge.upload_from_file(
    "knowledge/system-instructions.md",
    knowledge_name="system-instructions",
    knowledge_type="markdown",
    description="System instructions for the web search agent",
    visible=False,
)
```

**`web_search_sub_agent.py` (key lines):**

```python
# Fetch from server (or local provider) at runtime
agent = XiansContext.CurrentAgent
knowledge = await agent.knowledge.get_async("system-instructions")
system_prompt = knowledge.content if knowledge else "Default prompt"
```

---

## Architecture

### Component Diagram

```
XiansContext.CurrentAgent
        |
        | .knowledge (property)
        v
KnowledgeCollection              <-- Public facade (CRUD API)
        |
        | _provider
        v
KnowledgeProvider (Protocol)      <-- Abstract interface
        |
   +----|----+
   |         |
   v         v
ServerKnowledgeProvider     LocalKnowledgeProvider
  (HTTP + in-memory cache)    (in-memory + file fallback)
        |
        | Created by
        v
KnowledgeProviderFactory.create(local_mode, http_client, ...)
```

### Module Layout

```
src/xians/agents/knowledge/
    __init__.py                       # Exports KnowledgeCollection, KnowledgeItem
    models.py                         # KnowledgeItem Pydantic model
    knowledge_collection.py           # Public facade (get/update/delete/list)
    providers/
        __init__.py                   # Exports all providers
        interface.py                  # KnowledgeProvider Protocol
        server_provider.py            # HTTP-backed provider with cache
        local_provider.py             # In-memory provider for local_mode
        factory.py                    # KnowledgeProviderFactory
```

### How It Connects

1. **`AgentRegistration.knowledge`** (lazy property) creates a `KnowledgeCollection`
   using `KnowledgeProviderFactory.create(...)`.
2. The factory selects `ServerKnowledgeProvider` (production) or
   `LocalKnowledgeProvider` (local_mode) based on `XiansOptions.local_mode`.
3. `ServerKnowledgeProvider` uses the platform's `httpx.AsyncClient` (shared
   with `XiansServerClient`) for all HTTP calls.
4. `KnowledgeCollection` delegates to the provider and manages a local cache of
   recently accessed knowledge items.

### Server API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/knowledge/latest` | GET | Get knowledge (tenant-scoped, progressive fallback) |
| `/api/agent/knowledge/latest/system` | GET | Get system-scoped knowledge |
| `/api/agent/knowledge` | POST | Create or update knowledge |
| `/api/agent/knowledge` | DELETE | Delete knowledge |
| `/api/agent/knowledge/list` | GET | List all knowledge for an agent |

All endpoints use `X-Tenant-Id` header where applicable and support an optional
`activationName` query parameter.

---

## C# to Python Mapping

| C# | Python |
|----|--------|
| `agent.Knowledge.GetAsync("name")` | `await agent.knowledge.get_async("name")` |
| `agent.Knowledge.GetSystemAsync("name")` | `await agent.knowledge.get_system_async("name")` |
| `agent.Knowledge.UpdateAsync("name", content, type, ...)` | `await agent.knowledge.update_async("name", content, type=..., ...)` |
| `agent.Knowledge.DeleteAsync("name")` | `await agent.knowledge.delete_async("name")` |
| `agent.Knowledge.ListAsync()` | `await agent.knowledge.list_async()` |
| `agent.Knowledge.UploadEmbeddedResourceAsync(path, ...)` | `await agent.knowledge.upload_from_file(path, ...)` |
| `agent.Knowledge.UploadTextResourceAsync(name, content)` | `await agent.knowledge.upload_text(name, content)` |
| `agent.Knowledge.DisplayKnowledgeSummaryAsync()` | `await agent.knowledge.display_summary_async()` |
| `Knowledge` (model) | `KnowledgeItem` |
| `IKnowledgeProvider` | `KnowledgeProvider` (Protocol) |
| `ServerKnowledgeProvider` | `ServerKnowledgeProvider` |
| `LocalKnowledgeProvider` | `LocalKnowledgeProvider` (file-based, mirrors embedded resources) |
| `KnowledgeProviderFactory.Create(...)` | `KnowledgeProviderFactory.create(...)` |
| `KnowledgeCollection` | `KnowledgeCollection` |
| `XiansOptions.LocalMode` | `XiansOptions.local_mode` |
| `XiansOptions.LocalModeAssemblies` | `LOCAL_KNOWLEDGE_FOLDER` env var (Python has no assemblies) |

---

## See Also

- [SDK_ACCESS_PATTERNS.md](SDK_ACCESS_PATTERNS.md) — Where Knowledge fits in the four SDK access patterns
- [XIANSCONTEXT_CURRENT_AGENT_WORKFLOW.md](XIANSCONTEXT_CURRENT_AGENT_WORKFLOW.md) — How `CurrentAgent` resolves
- [Knowledge Concepts](https://docs.xians.ai/concepts/knowledge) — Xians platform knowledge documentation
