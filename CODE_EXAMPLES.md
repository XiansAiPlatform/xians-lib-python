# Quick Reference: Key Code Examples

This document provides quick code examples for using the new Xians Server API contracts.

## 1. Flow Definition Upload

### Creating and Uploading a Flow Definition

```python
from xians.models.v1.server_contracts import (
    ParameterDefinition,
    ActivityDefinitionRequest,
    FlowDefinitionRequest,
)
from xians.interfaces.v1.xians_client import XiansServerClient

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
    name="Main Workflow",
    activity_definitions=[activity],
    parameter_definitions=[param],
    system_scoped=False,
)

# Upload to server
response = await client.upload_flow_definition(flow)
```

### Payload Sent to Server

```json
{
  "agent": "MyAgent",
  "workflowType": "Conversational",
  "name": "Main Workflow",
  "activityDefinitions": [
    {
      "activityName": "process_message",
      "knowledgeIds": ["kb_001"],
      "parameterDefinitions": [
        {
          "name": "input_message",
          "type": "string"
        }
      ]
    }
  ],
  "parameterDefinitions": [
    {
      "name": "input_message",
      "type": "string"
    }
  ],
  "systemScoped": false
}
```

## 2. Conversation Outbound Messages

### Send Chat Message

```python
from xians.models.v1.server_contracts import ChatOrDataRequest

req = ChatOrDataRequest(
    participant_id="user_123",
    workflow_id="workflow_456",
    text="Hello! How can I help?",
)

response = await client.send_outbound_chat(req)
```

### Send Data Payload

```python
req = ChatOrDataRequest(
    participant_id="user_123",
    data={
        "action": "update_status",
        "status": "completed",
        "metadata": {"timestamp": "2026-01-07T10:00:00Z"}
    },
)

response = await client.send_outbound_data(req)
```

### Send Handoff

```python
from xians.models.v1.server_contracts import HandoffRequest

req = HandoffRequest(
    participant_id="user_123",
    target="human_agent",
    reason="User requested escalation",
    text="Transferring to human support team",
)

response = await client.send_handoff(req)
```

### Payloads Sent to Server

**Chat:**
```json
{
  "participantId": "user_123",
  "workflowId": "workflow_456",
  "text": "Hello! How can I help?"
}
```

**Data:**
```json
{
  "participantId": "user_123",
  "data": {
    "action": "update_status",
    "status": "completed",
    "metadata": {"timestamp": "2026-01-07T10:00:00Z"}
  }
}
```

**Handoff:**
```json
{
  "participantId": "user_123",
  "target": "human_agent",
  "reason": "User requested escalation",
  "text": "Transferring to human support team"
}
```

## 3. Usage Reporting

### Report Token Usage

```python
from xians.models.v1.server_contracts import UsageReportRequest

req = UsageReportRequest(
    model="gpt-4",
    prompt_tokens=150,
    completion_tokens=75,
    total_tokens=225,
    message_count=2,
    response_time_ms=1200,
    metadata={"region": "us-east-1", "version": "1.0"},
)

response = await client.report_usage(req)
```

### Payload Sent to Server

```json
{
  "model": "gpt-4",
  "promptTokens": 150,
  "completionTokens": 75,
  "totalTokens": 225,
  "messageCount": 2,
  "responseTimeMs": 1200,
  "metadata": {"region": "us-east-1", "version": "1.0"}
}
```

## 4. Knowledge Management

### Get Latest Knowledge

```python
kb = await client.get_latest_knowledge(
    name="product_faq",
    agent="MyAgent",
)
# Endpoint: GET /api/agent/knowledge/latest?name=product_faq&agent=MyAgent
```

### List All Knowledge

```python
all_kb = await client.list_knowledge(agent="MyAgent")
# Endpoint: GET /api/agent/knowledge/list?agent=MyAgent
```

### Create New Knowledge

```python
kb = await client.create_knowledge(
    name="product_faq",
    agent="MyAgent",
    type="document",
    content="Q: What is your product? A: It is...",
)
# Endpoint: POST /api/agent/knowledge
```

### Delete Knowledge

```python
response = await client.delete_knowledge(
    name="product_faq",
    agent="MyAgent",
)
# Endpoint: DELETE /api/agent/knowledge?name=product_faq&agent=MyAgent
```

## 5. Document Management

### Save Document

```python
doc = {
    "title": "User Profile",
    "user_id": "user_123",
    "email": "user@example.com",
}

response = await client.save_document(
    document=doc,
    options={"index": True, "ttl": 3600},
)
# Endpoint: POST /api/agent/documents/save
```

### Get Document by ID

```python
doc = await client.get_document(id="doc_789")
# Endpoint: POST /api/agent/documents/get
# Payload: {"id": "doc_789"}
```

### Get Document by Key

```python
doc = await client.get_document_by_key(
    type="user_profile",
    key="user_123",
)
# Endpoint: POST /api/agent/documents/get-by-key
# Payload: {"type": "user_profile", "key": "user_123"}
```

### Query Documents

```python
results = await client.query_documents(
    query={"field": "status", "value": "active"},
    content_type="application/json",
)
# Endpoint: POST /api/agent/documents/query
```

### Update Document

```python
doc = {"id": "doc_789", "title": "Updated Title"}
response = await client.update_document(document=doc)
# Endpoint: POST /api/agent/documents/update
```

### Delete Document

```python
response = await client.delete_document(id="doc_789")
# Endpoint: POST /api/agent/documents/delete
```

### Delete Multiple Documents

```python
response = await client.delete_many_documents(
    ids=["doc_789", "doc_790", "doc_791"]
)
# Endpoint: POST /api/agent/documents/delete-many
```

### Check if Document Exists

```python
result = await client.document_exists(id="doc_789")
# Returns: {"exists": true} or {"exists": false}
# Endpoint: POST /api/agent/documents/exists
```

## 6. Validation Examples

### What Gets Rejected

```python
from pydantic import ValidationError

# ✗ Empty participant ID
try:
    ChatOrDataRequest(participant_id="")
except ValidationError as e:
    print(e)  # Field cannot be empty

# ✗ Missing activity definitions
try:
    FlowDefinitionRequest(
        agent="MyAgent",
        workflow_type="Conversational",
        activity_definitions=[],  # Must have >= 1
        parameter_definitions=[ParameterDefinition(name="p1", type="string")],
    )
except ValidationError as e:
    print(e)  # Ensure this value has at least 1 items

# ✗ Negative token count
try:
    UsageReportRequest(
        prompt_tokens=-1,  # Must be >= 0
        completion_tokens=50,
        total_tokens=50,
        message_count=1,
    )
except ValidationError as e:
    print(e)  # Value must be >= 0
```

## 7. Error Handling

### Catching and Inspecting Errors

```python
from xians.exceptions.v1.errors import XiansServerError

try:
    response = await client.upload_flow_definition(flow)
except XiansServerError as e:
    print(f"Status Code: {e.status_code}")
    print(f"Method: {e.method}")
    print(f"URL: {e.url}")
    print(f"Response Body: {e.response_body}")
    
    # Special handling for 400 errors
    if e.status_code == 400:
        print("Payload validation failed on server side")
        print("Response indicated:", e.response_body)
```

## 8. Migration from Old API

### Before (Deprecated)

```python
# Old definition upload
await client.upload_workflow_definition(agent_def, workflow_def)

# Old outbound message
await client.send_outbound_message(conv_id, "Hello")

# Old usage event
await client.send_usage_event({"tokens": 100})

# Old knowledge - non-existent endpoint!
await client.fetch_knowledge("query", top_k=5)

# Old document - non-existent endpoint!
doc = await client.fetch_document("doc_id")
```

### After (Current)

```python
# New definition upload
flow_def = FlowDefinitionRequest(...)
await client.upload_flow_definition(flow_def)

# New outbound chat
chat_req = ChatOrDataRequest(participant_id=user_id, text="Hello")
await client.send_outbound_chat(chat_req)

# New usage report
usage = UsageReportRequest(
    prompt_tokens=50,
    completion_tokens=100,
    total_tokens=150,
    message_count=1,
)
await client.report_usage(usage)

# New knowledge
kb = await client.get_latest_knowledge("kb_name", "agent")

# New document  
doc = await client.get_document("doc_id")  # POST method
```

## 9. Full Workflow Example

```python
from xians.models.v1.server_contracts import (
    ParameterDefinition,
    ActivityDefinitionRequest,
    FlowDefinitionRequest,
    ChatOrDataRequest,
    UsageReportRequest,
)

# 1. Define a flow
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

# 2. Upload the flow
await client.upload_flow_definition(flow)

# 3. Send a chat message
chat = ChatOrDataRequest(
    participant_id="user_123",
    text="Hello bot!",
)
await client.send_outbound_chat(chat)

# 4. Report usage
usage = UsageReportRequest(
    prompt_tokens=20,
    completion_tokens=10,
    total_tokens=30,
    message_count=1,
)
await client.report_usage(usage)

# 5. Manage knowledge
kb = await client.get_latest_knowledge("kb_001", "MyBot")

# 6. Store conversation in documents
doc = {
    "conversation_id": "conv_123",
    "user_id": "user_123",
    "messages": [{"role": "user", "content": "Hello bot!"}],
}
await client.save_document(document=doc)
```

