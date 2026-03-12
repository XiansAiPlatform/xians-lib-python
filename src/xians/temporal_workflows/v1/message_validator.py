"""Validates incoming messages for tenant isolation and agent name. Matches C# MessageValidator."""

import logging
from typing import Optional

from .models import WorkflowHandlerMetadata
from .tenant_context import TenantContext

logger = logging.getLogger(__name__)


def validate_tenant_isolation(
    workflow_tenant_id: str,
    metadata: WorkflowHandlerMetadata,
) -> bool:
    """Validate workflow tenant matches handler's tenant (for non-system-scoped agents)."""
    return TenantContext.validate_tenant_isolation(
        metadata.tenant_id or "",
        workflow_tenant_id or "",
        metadata.system_scoped,
    )


def validate_agent_name(
    message_agent: Optional[str],
    metadata: WorkflowHandlerMetadata,
    request_id: str,
) -> bool:
    """Validate that the message's agent name matches the registered handler's agent name."""
    expected = (metadata.agent_name or "").strip()
    received = (message_agent or "").strip()
    if expected != received:
        logger.warning(
            "Agent name mismatch: expected=%s received=%s request_id=%s",
            expected,
            message_agent,
            request_id,
        )
        return False
    return True
