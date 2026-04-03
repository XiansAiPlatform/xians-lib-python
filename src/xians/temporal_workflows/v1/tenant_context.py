"""Tenant context utilities matching C# TenantContext."""

from typing import Optional


class WorkflowIdError(Exception):
    """Raised when a workflow ID is invalid (null/empty or wrong format).

    Mirrors C# WorkflowException thrown by TenantContext.ValidateAndSplitWorkflowId.
    """

    def __init__(self, message: str, workflow_id: Optional[str] = None) -> None:
        self.workflow_id = workflow_id
        super().__init__(message)


class TenantContext:
    """Utility for tenant context operations. Matches C# TenantContext."""

    @staticmethod
    def _validate_and_split(
        workflow_id: Optional[str],
        min_parts: int,
        expected_format: str,
    ) -> list[str]:
        """Validate and split a workflow ID. Matches C# ValidateAndSplitWorkflowId."""
        if not workflow_id or not workflow_id.strip():
            raise WorkflowIdError(
                "WorkflowId cannot be null or empty.", workflow_id
            )
        parts = workflow_id.split(":")
        if len(parts) < min_parts:
            raise WorkflowIdError(
                f"Invalid WorkflowId format. Expected '{expected_format}', got '{workflow_id}'",
                workflow_id,
            )
        return parts

    @staticmethod
    def extract_tenant_id(workflow_id: str) -> str:
        """Extract tenant ID from workflow ID (first segment before ':').

        Raises ``WorkflowIdError`` if the workflow ID is empty or has fewer
        than 2 colon-separated segments, matching C# TenantContext.ExtractTenantId.
        """
        parts = TenantContext._validate_and_split(
            workflow_id, 2, "TenantId:WorkflowType:..."
        )
        return parts[0]

    @staticmethod
    def extract_workflow_type(workflow_id: str) -> Optional[str]:
        """Extract workflow type from workflow ID."""
        parts = workflow_id.split(":")
        if len(parts) >= 3:
            return f"{parts[1]}:{parts[2]}"
        return None

    @staticmethod
    def get_task_queue_name(
        workflow_type: str,
        system_scoped: bool,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Build task queue name. Matches C# TenantContext.GetTaskQueueName."""
        if system_scoped:
            return workflow_type
        if not tenant_id:
            raise ValueError("tenant_id required for non-system-scoped workflows")
        return f"{tenant_id}:{workflow_type}"

    @staticmethod
    def build_workflow_id(
        tenant_id: str,
        workflow_type: str,
        *suffix_parts: str,
    ) -> str:
        """Build a full workflow ID."""
        parts = [tenant_id, workflow_type]
        parts.extend(suffix_parts)
        return ":".join(parts)

    @staticmethod
    def validate_tenant_isolation(
        request_tenant_id: str,
        workflow_tenant_id: str,
        system_scoped: bool,
    ) -> bool:
        """Validate tenant isolation for non-system workflows."""
        if system_scoped:
            return True
        return request_tenant_id == workflow_tenant_id
