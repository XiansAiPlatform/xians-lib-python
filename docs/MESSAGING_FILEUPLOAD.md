# File Upload Messaging

File uploads allow client applications to send files (documents, images, etc.) to agent workflows. The SDK routes file uploads to dedicated `on_file_upload` handlers when messages use the **`File`** message type — a first-class type with the base64-encoded file in the `data` payload.

> **Important:** File uploads use `type: "File"` (not `Chat`, `Webhook` or `Data`). The `File` type routes directly to `on_file_upload` handlers.

## Listening for File Uploads on the Agent

Register a file upload handler on your built-in workflow using `on_file_upload`:

```python
import base64
import json
from xians.agents.messaging import UserMessageContext

async def my_file_handler(context: UserMessageContext) -> None:
    raw_data = context.message.data

    if isinstance(raw_data, dict):
        base64_content = raw_data.get("content", "")
        file_name = raw_data.get("fileName")
    elif isinstance(raw_data, str):
        base64_content = raw_data
        file_name = context.message.text
    else:
        base64_content = str(raw_data) if raw_data else ""
        file_name = context.message.text

    if not base64_content:
        await context.reply_async("No file data received.")
        return

    try:
        file_bytes = base64.b64decode(base64_content)
        await context.reply_async(
            f"File received! Processed {len(file_bytes)} bytes. "
            f"Name: {file_name or 'uploaded-file'}"
        )
    except Exception:
        await context.reply_async(
            "Invalid file format. Please ensure the file is base64 encoded."
        )


conversational_workflow = xians_agent.workflows.define_builtin(name="Conversational")
conversational_workflow.on_file_upload(my_file_handler)
```

### Handler Context

The handler receives a `UserMessageContext` (same as `on_user_chat_message` and `on_user_data_message`). Key properties:

| Property | Description |
|----------|-------------|
| `context.message.data` | The base64 encoded file content (string or object containing it) |
| `context.message.text` | Optional text (e.g., caption, filename) if sent by client |
| `context.message.participant_id` | User identifier who sent the file |
| `context.message.request_id` | Request tracking ID |
| `context.message.tenant_id` | Tenant context |

### Accessing Metadata

Clients may send an object in `data` with both the file content and metadata:

```json
{
  "content": "base64EncodedFileContentHere...",
  "fileName": "report.pdf",
  "contentType": "application/pdf"
}
```

In your handler, extract the content and metadata accordingly:

```python
async def my_file_handler(context: UserMessageContext) -> None:
    raw_data = context.message.data

    if isinstance(raw_data, dict):
        base64_content = raw_data.get("content", "")
        file_name = raw_data.get("fileName")
        content_type = raw_data.get("contentType")
    elif isinstance(raw_data, str):
        base64_content = raw_data
        file_name = None
        content_type = None
    else:
        base64_content = str(raw_data) if raw_data else ""
        file_name = None
        content_type = None

    import base64
    file_bytes = base64.b64decode(base64_content)
    # Process with optional file_name, content_type...
```

### Replying to the User

Use the same reply methods as other message handlers:

- `await context.reply_async("Thank you for the file.")`
- `await context.send_data_async({"status": "processed", "size": len(file_bytes)})`
- `await context.get_chat_history_async()` to access conversation history

---

## Sending File Uploads from Client Applications

Use the **Messaging Admin API** to send file upload messages from your client application.

### Endpoint

```
POST /api/v1/admin/tenants/{tenantId}/messaging/send
```

### Required Request Body Fields

| Field | Type | Description |
|-------|------|-------------|
| `agentName` | string | Name of the target agent |
| `activationName` | string | Name of the activation (workflow instance) |
| `participantId` | string | Identifier of the user sending the file |
| `type` | string | Must be **`"File"`** |
| `data` | string or object | The base64 encoded file content |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Optional caption or filename |
| `workflowType` | string | Workflow type (default: `"Supervisor Workflow"`). Use `"Conversational"` for conversational workflows. |
| `topic` | string | Scope/topic for organizing the message thread |
| `requestId` | string | Custom request ID (auto-generated if omitted) |
| `hint` | string | Hint for the agent |
| `authorization` | string | Auth token (or use `Authorization` header) |

### Example: Minimal Format (Base64 String in Data)

```bash
curl -X POST "https://your-server/api/v1/admin/tenants/default/messaging/send" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agentName": "DocumentAgent",
    "activationName": "DocumentAgent - Default",
    "participantId": "user@example.com",
    "type": "File",
    "data": "JVBERi0xLjQK..."
  }'
```

### Example: Rich Format (Object with Metadata)

```bash
curl -X POST "https://your-server/api/v1/admin/tenants/default/messaging/send" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agentName": "DocumentAgent",
    "activationName": "DocumentAgent - Default",
    "participantId": "user@example.com",
    "type": "File",
    "text": "invoice.pdf",
    "data": {
      "content": "JVBERi0xLjQK...",
      "fileName": "invoice.pdf",
      "contentType": "application/pdf",
      "fileSize": 1024
    },
    "topic": "document-uploads"
  }'
```

---

## Summary

| Aspect | Detail |
|--------|--------|
| **Agent registration** | `workflow.on_file_upload(handler)` |
| **Message type** | `File` |
| **Data field** | Base64 encoded file (string or object with `content` and optional metadata) |
| **Text field** | Optional (caption, filename) |
| **API endpoint** | `POST /api/v1/admin/tenants/{tenantId}/messaging/send` |
| **Required API fields** | `agentName`, `activationName`, `participantId`, `type: "File"`, `data` |

## Related

- [Replying to User Messages](./MESSAGING_REPLYING.md) — Full messaging and response methods
- [Message Progress](./MESSAGING_PROGRESS.md) — Reasoning and tool execution messages
