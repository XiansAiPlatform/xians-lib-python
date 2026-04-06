# Document DB

## Flexible Data Storage for AI Agents

Your agents need to **remember things**. Customer profiles, order history, session data, analytics — structured information that doesn't fit neatly into prompts. Document DB gives your agents a schema-less, queryable memory that scales.

## Architecture

The Python Document DB implementation mirrors the C# `Xians.Lib.Agents.Documents` architecture:

```
agents/documents/
├── models/
│   ├── document.py          # Document model (Pydantic)
│   ├── document_options.py   # Storage options (TTL, overwrite, key-as-id)
│   └── document_query.py     # Query parameters (filters, pagination, sort)
├── document_service.py       # HTTP layer (XiansServerClient calls)
├── document_activities.py    # Temporal activities (deterministic wrapper)
├── document_executor.py      # Context-aware executor (workflow vs direct)
└── document_collection.py    # High-level agent API (scoping, validation)
```

### Layered Design

| Layer | Class | Responsibility |
|-------|-------|----------------|
| **Models** | `Document`, `DocumentOptions`, `DocumentQuery` | Data contracts (Pydantic models with camelCase API serialization) |
| **Service** | `DocumentService` | Direct HTTP operations via `XiansServerClient` |
| **Activities** | `DocumentActivities` | Temporal activities wrapping `DocumentService` for workflow safety |
| **Executor** | `DocumentActivityExecutor` | Context-aware routing: workflow → activities, activity/direct → service |
| **Collection** | `DocumentCollection` | Agent-facing API with automatic scoping, validation, ownership checks |

### Context-Aware Execution

The executor automatically detects the execution context:

- **Inside a Temporal workflow**: Routes through `DocumentActivities` (Temporal activities) to keep workflows deterministic
- **Inside a Temporal activity or direct call**: Calls `DocumentService` directly for HTTP operations

This matches the C# `ContextAwareActivityExecutor` pattern.

## Quick Start

### Access from Agent Registration

```python
agent = platform.agents.register(
    XiansAgentRegistration(name="My Agent", is_template=True)
)

# Access documents collection (lazy-initialized)
docs = agent.documents
```

### Access from Workflow/Activity Context

```python
from xians.agents.core import XiansContext

# Inside a Temporal activity:
docs = XiansContext.Documents
# or
docs = XiansContext.CurrentAgent.documents
```

## Understanding Type and Key

### Type: Your Document Categories

`type` organizes documents into logical groups:

```python
doc.type = "user-profile"      # Customer data
doc.type = "session"           # Active sessions
doc.type = "order"             # Purchase history
doc.type = "preferences"       # User settings
doc.type = "analytics-event"   # Event logs
```

### Key: Your Semantic Identifier

`key` is a human-readable, business-meaningful identifier:

```python
doc.key = "user-12345"          # User ID from your system
doc.key = "session-abc-def"     # Session identifier
doc.key = "order-2024-001"      # Order number
doc.key = "config-email-smtp"   # Configuration name
```

### Type + Key: Unique Lookup

The combination of `type` + `key` creates a unique identifier for each document (enabled by default via `UseKeyAsIdentifier`):

```python
from xians.agents.documents import Document, DocumentOptions

doc = Document(
    type="user-preferences",
    key=f"user-{user_id}",
    content={"theme": "dark", "language": "en"},
)

# Type+Key becomes the unique identifier by default
# Saving again with same type+key updates the existing document
saved = await agent.documents.save_async(doc)

# Retrieve directly with Type + Key
user_prefs = await agent.documents.get_by_key_async("user-preferences", f"user-{user_id}")
```

## Core Operations

### Default Behaviors

Document DB comes with sensible defaults:

- **`use_key_as_identifier = True`** — documents are uniquely identified by Type+Key
- **`overwrite = True`** — saving same Type+Key updates the existing document
- **`ttl_minutes = None`** — documents persist indefinitely unless TTL is set

Override any of these by explicitly passing `DocumentOptions`.

### Save & Retrieve

```python
from xians.agents.documents import Document

profile = Document(
    type="user-profile",
    content={"name": "Alice", "plan": "premium", "credits": 1000},
)

saved = await agent.documents.save_async(profile)

# Get it back
retrieved = await agent.documents.get_async(saved.id)
```

### Working with Type + Key

```python
# User preferences: One document per user
await agent.documents.save_async(Document(
    type="user-preferences",
    key=f"user-{user_id}",
    content=preferences,
))

# Configuration: Named settings
await agent.documents.save_async(Document(
    type="config",
    key="email-templates",
    content=templates,
))

# Retrieve by Type + Key — no GUID needed!
user_prefs = await agent.documents.get_by_key_async("user-preferences", f"user-{user_id}")
email_config = await agent.documents.get_by_key_async("config", "email-templates")
```

### Query & Filter

```python
from xians.agents.documents import DocumentQuery

# Query by type — automatically scoped to current agent and context
active_users = await agent.documents.query_async(DocumentQuery(
    type="user-profile",
    metadata_filters={"status": "active", "plan": "premium"},
    limit=50,
))
```

**Automatic Query Scoping:**
- `agent_id` is always set to limit results to your agent's documents
- When in workflow context, `activation_name` and `participant_id` are auto-populated
- Override these by setting them explicitly in your query

### Update & Delete

```python
# Update (document must have an ID)
profile.content = {"credits": 500}
await agent.documents.update_async(profile)

# Delete one
await agent.documents.delete_async(profile_id)

# Delete many
await agent.documents.delete_many_async([id1, id2, id3])

# Check existence
exists = await agent.documents.exists_async(profile_id)
```

## Advanced Features

### Time-to-Live (TTL)

Documents persist indefinitely by default. Set expiration for temporary data:

```python
from xians.agents.documents import Document, DocumentOptions

session = Document(
    type="session",
    key=session_id,
    content={"token": "abc123"},
)

await agent.documents.save_async(
    session,
    options=DocumentOptions(ttl_minutes=60),  # Expires in 1 hour
)
```

### Metadata Enrichment

Every document is automatically enriched:

**Always Populated:**
- `agent_id` — the agent name that owns this document
- `created_at`, `updated_at` — automatic timestamps
- `expires_at` — only set when TTL is specified

**Populated When in Workflow/Activity Context:**
- `workflow_id` — the specific workflow instance
- `activation_name` — workflow type postfix for context-based scoping
- `participant_id` — participant/user context for user-specific isolation

### Multi-Level Document Scoping

Documents are automatically scoped at multiple levels:

**1. Agent-Level Scoping**

```python
# Agent "OrderProcessor" saves a document
doc = await order_agent.documents.save_async(my_doc)

# Agent "UserManager" tries to access it
result = await user_agent.documents.get_async(doc.id)
# Returns None — different agent, access denied
```

**2. Context-Based Scoping (When in Workflows)**

```python
# Documents saved in workflow context are automatically scoped
session_doc = await agent.documents.save_async(Document(
    type="session",
    key="current-state",
    content=session_data,
))
# Automatically populated: agent_id, activation_name, participant_id, workflow_id
```

**3. Tenant-Level Isolation**

All operations include tenant isolation via the `X-Tenant-Id` header.

### Custom DocumentOptions

```python
from xians.agents.documents import DocumentOptions

# Disable key-as-identifier (use server-generated IDs)
options = DocumentOptions(use_key_as_identifier=False)

# Disable overwrite (fail if document exists)
options = DocumentOptions(overwrite=False)

# Set TTL
options = DocumentOptions(ttl_minutes=120)

# Combine options
options = DocumentOptions(
    ttl_minutes=30,
    overwrite=True,
    use_key_as_identifier=True,
)
```

## API Reference

### DocumentCollection Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `save_async(document, options?)` | Save/upsert a document | `Document` |
| `get_async(id)` | Get document by ID | `Document \| None` |
| `get_by_key_async(type, key)` | Get document by Type+Key | `Document \| None` |
| `query_async(query)` | Query with filters | `list[Document]` |
| `update_async(document)` | Update existing document | `bool` |
| `delete_async(id)` | Delete by ID | `bool` |
| `delete_many_async(ids)` | Delete multiple | `int` (count) |
| `exists_async(id)` | Check existence | `bool` |

### Document Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str?` | Unique ID (auto-generated if not provided) |
| `key` | `str?` | Semantic key identifier |
| `type` | `str?` | Document type/category |
| `content` | `Any?` | JSON-serializable content |
| `metadata` | `dict?` | Optional metadata for filtering |
| `agent_id` | `str?` | Owning agent (auto-populated) |
| `workflow_id` | `str?` | Workflow instance (auto-populated) |
| `activation_name` | `str?` | Workflow type postfix (auto-populated) |
| `participant_id` | `str?` | Participant/user context (auto-populated) |
| `created_at` | `datetime?` | Creation timestamp |
| `updated_at` | `datetime?` | Last update timestamp |
| `expires_at` | `datetime?` | Expiration time (when TTL is set) |
| `created_by` | `str?` | Creating user |
| `updated_by` | `str?` | Last updating user |

### DocumentQuery Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `str?` | `None` | Filter by document type |
| `key` | `str?` | `None` | Filter by document key |
| `agent_id` | `str?` | Auto-set | Filter by agent (auto-scoped) |
| `activation_name` | `str?` | Auto-set | Filter by activation name |
| `participant_id` | `str?` | Auto-set | Filter by participant |
| `metadata_filters` | `dict?` | `None` | AND-combined metadata filters |
| `limit` | `int?` | `100` | Max results |
| `skip` | `int?` | `0` | Pagination offset |
| `sort_by` | `str?` | `None` | Sort field |
| `sort_descending` | `bool` | `True` | Sort direction |
| `created_after` | `datetime?` | `None` | Created after filter |
| `created_before` | `datetime?` | `None` | Created before filter |

## Common Patterns

### Document Organization by Type

```
Agent: "OrderProcessingAgent"
├── Type: "user-profile"
│   ├── Key: "user-001" → { name, email, plan }
│   └── Key: "user-002" → { name, email, plan }
│
├── Type: "order"
│   ├── Key: "order-2024-001" → { items, total, status }
│   └── Key: "order-2024-002" → { items, total, status }
│
├── Type: "session"  (TTL: 30 min)
│   └── Key: "session-abc" → { userId, cart, expires }
│
└── Type: "config"
    ├── Key: "payment-gateway" → { apiKey, endpoint }
    └── Key: "shipping-rates" → { zones, rates }
```

### User Preferences Store

```python
async def save_user_preferences(user_id: str, prefs: dict) -> None:
    doc = Document(
        type="user-preferences",
        key=user_id,
        content=prefs,
    )
    await agent.documents.save_async(doc)
```

### Session Cache with TTL

```python
session = Document(
    type="session",
    key=session_id,
    content=session_data,
)
await agent.documents.save_async(
    session,
    options=DocumentOptions(ttl_minutes=30),
)
```

### Event Log with Metadata

```python
event = Document(
    type="analytics-event",
    content={
        "event": "purchase",
        "user_id": user_id,
        "amount": 99.99,
    },
    metadata={"category": "revenue", "priority": "high"},
)
await agent.documents.save_async(event)
```

## What Document DB Is

- **Schema-less** — Store any JSON structure
- **Multi-level scoping** — Automatic agent, context, and tenant isolation
- **Context-aware** — Workflow-based ActivationName and ParticipantId scoping
- **Type-based categorization** — Organize by document type
- **Semantic keys** — Human-readable identifiers (enabled by default)
- **Type + Key lookup** — Direct retrieval without GUIDs
- **Update-friendly** — Overwrites existing documents by default
- **Persistent by default** — Documents last indefinitely unless TTL is set
- **Optional TTL** — Auto-expire temporary data when needed
- **Auto-scoped queries** — Queries automatically limited to your scope
- **Queryable** — Filter by type, metadata, keys, dates

## What Document DB Is NOT

- Not a relational database (no joins)
- Not for large binary files (use blob storage)
- Not for high-frequency writes (use caching layers)

Document DB is your agent's **persistent memory**. Use it for configuration, state, user data, and anything your agent needs to remember between executions.
