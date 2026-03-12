"""WebhookContext - context for webhook handlers. Matches C# WebhookContext."""

import json
from dataclasses import dataclass
from typing import Any, Optional

from ...temporal_workflows.v1.models import WebhookResponse


@dataclass
class WebhookMessage:
    """Webhook message data. Matches C# WebhookMessage."""
    participant_id: str = ""
    scope: str = ""
    name: str = ""
    payload: Any = None
    authorization: Optional[str] = None
    request_id: str = ""
    tenant_id: str = ""


class WebhookContext:
    """Context passed to webhook handlers. Matches C# WebhookContext."""

    def __init__(self, webhook: WebhookMessage):
        self.webhook = webhook
        self.response = WebhookResponse()

    def respond(self, content: Any) -> None:
        """Set the webhook response.

        Args:
            content: str for raw content, or any object for JSON serialization
        """
        if isinstance(content, str):
            self.response = WebhookResponse(
                status_code=200,
                content=content,
                content_type="application/json",
            )
        else:
            self.response = WebhookResponse(
                status_code=200,
                content=json.dumps(content, default=str),
                content_type="application/json",
            )

    def respond_with(self, response: WebhookResponse) -> None:
        """Set a full webhook response."""
        self.response = response
