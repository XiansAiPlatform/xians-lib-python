"""Data models for temporal workflows. Matches C# workflow data contracts.

InboundMessage / InboundMessagePayload use camelCase field names because the
C# Xians server sends camelCase JSON via Temporal signals.  The default
Temporal Python SDK converter matches on field names exactly, so these must
match the wire format.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional


@dataclass
class InboundMessagePayload:
    """Matches C# InboundMessagePayload.  Field names are camelCase to match
    the JSON sent by the Xians server through Temporal signals.

    All string fields are Optional because the C# server sends ``null``
    for unset values."""
    agent: Optional[str] = ""
    threadId: Optional[str] = ""
    participantId: Optional[str] = ""
    authorization: Optional[str] = None
    text: Optional[str] = ""
    requestId: Optional[str] = ""
    hint: Optional[str] = ""
    scope: Optional[str] = ""
    data: Any = None
    type: Optional[str] = "chat"
    history: Optional[list] = None

    def __post_init__(self) -> None:
        if not self.requestId:
            self.requestId = str(uuid.uuid4())

    @property
    def participant_id(self) -> str:
        return self.participantId or ""

    @property
    def thread_id(self) -> str:
        return self.threadId or ""

    @property
    def request_id(self) -> str:
        return self.requestId or ""


@dataclass
class InboundMessage:
    """Matches C# InboundMessage.  Field names are camelCase to match the
    JSON sent by the Xians server through Temporal signals."""
    payload: InboundMessagePayload = field(default_factory=InboundMessagePayload)
    sourceAgent: Optional[str] = ""
    sourceWorkflowId: Optional[str] = ""
    sourceWorkflowType: Optional[str] = ""

    @property
    def source_agent(self) -> str:
        return self.sourceAgent or ""

    @property
    def source_workflow_id(self) -> str:
        return self.sourceWorkflowId or ""

    @property
    def source_workflow_type(self) -> str:
        return self.sourceWorkflowType or ""


@dataclass
class WorkflowHandlerMetadata:
    """Matches C# WorkflowHandlerMetadata."""
    agent_name: str = ""
    tenant_id: Optional[str] = None
    system_scoped: bool = False
    chat_handler: Optional[Callable] = None
    data_handler: Optional[Callable] = None
    file_upload_handler: Optional[Callable] = None
    webhook_handler: Optional[Callable] = None


@dataclass
class WorkflowOptions:
    """Matches C# WorkflowOptions."""
    max_history_length: int = 1000
    inactivity_timeout: Optional[float] = None


@dataclass
class ProcessMessageActivityRequest:
    """Matches C# ProcessMessageActivityRequest.

    String fields use Optional[str] because the C# server may send null
    for unset values.  The Temporal converter rejects None for plain ``str``.
    """
    message_text: Optional[str] = ""
    participant_id: Optional[str] = ""
    request_id: Optional[str] = ""
    scope: Optional[str] = ""
    hint: Optional[str] = ""
    data: Any = None
    tenant_id: Optional[str] = ""
    workflow_id: Optional[str] = ""
    workflow_type: Optional[str] = ""
    authorization: Optional[str] = None
    thread_id: Optional[str] = ""
    metadata: Optional[dict[str, str]] = None
    message_type: Optional[str] = "chat"


@dataclass
class SendMessageRequest:
    """Matches C# SendMessageRequest."""
    participant_id: Optional[str] = ""
    workflow_id: Optional[str] = ""
    workflow_type: Optional[str] = ""
    request_id: Optional[str] = ""
    scope: Optional[str] = ""
    data: Any = None
    authorization: Optional[str] = None
    text: Optional[str] = ""
    thread_id: Optional[str] = ""
    hint: Optional[str] = ""
    task_id: Optional[str] = None
    origin: Optional[str] = None
    type: Optional[str] = "chat"
    tenant_id: Optional[str] = ""


@dataclass
class SendHandoffRequest:
    """Matches C# SendHandoffRequest."""
    target_workflow_id: Optional[str] = ""
    target_workflow_type: Optional[str] = ""
    source_agent: Optional[str] = ""
    source_workflow_type: Optional[str] = ""
    source_workflow_id: Optional[str] = ""
    thread_id: Optional[str] = ""
    participant_id: Optional[str] = ""
    authorization: Optional[str] = None
    text: Optional[str] = ""
    data: Any = None
    tenant_id: Optional[str] = ""


@dataclass
class CurrentMessage:
    """Context data available to message handlers."""
    text: Optional[str] = ""
    participant_id: Optional[str] = ""
    request_id: Optional[str] = ""
    scope: Optional[str] = ""
    hint: Optional[str] = ""
    data: Any = None
    tenant_id: Optional[str] = ""
    workflow_id: Optional[str] = ""
    workflow_type: Optional[str] = ""
    authorization: Optional[str] = None
    thread_id: Optional[str] = ""
    message_type: Optional[str] = "chat"


@dataclass
class WebhookResponse:
    """Response from webhook handler. Matches C# WebhookResponse with factory methods."""
    status_code: int = 200
    content: str = ""
    content_type: str = "application/json"
    headers: Optional[dict[str, str]] = None

    @staticmethod
    def ok(content: str = "", content_type: str = "application/json") -> "WebhookResponse":
        return WebhookResponse(status_code=200, content=content, content_type=content_type)

    @staticmethod
    def error(content: str = "Internal Server Error", status_code: int = 500) -> "WebhookResponse":
        return WebhookResponse(status_code=status_code, content=content, content_type="text/plain")

    @staticmethod
    def bad_request(content: str = "Bad Request") -> "WebhookResponse":
        return WebhookResponse(status_code=400, content=content, content_type="text/plain")

    @staticmethod
    def not_found(content: str = "Not Found") -> "WebhookResponse":
        return WebhookResponse(status_code=404, content=content, content_type="text/plain")

    @staticmethod
    def internal_server_error(content: str = "Internal Server Error") -> "WebhookResponse":
        return WebhookResponse(status_code=500, content=content, content_type="text/plain")


@dataclass
class DbMessage:
    """Database message record. Matches C# DbMessage."""
    id: str = ""
    thread_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    direction: str = ""
    text: str = ""
    status: str = ""
    data: Any = None
    participant_id: str = ""
    workflow_id: str = ""
    workflow_type: str = ""
    request_id: str = ""
