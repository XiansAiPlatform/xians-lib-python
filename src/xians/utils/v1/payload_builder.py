"""Helper utilities for building Xians Server API payloads."""

import logging
from typing import Any

from ...models.v1.entities import AgentDefinition, WorkflowDefinition
from ...models.v1.payloads import WorkflowDefinitionPayload

logger = logging.getLogger(__name__)


def build_workflow_definition_payload(
    agent: AgentDefinition,
    workflow: WorkflowDefinition,
) -> dict[str, Any]:
    """
    Build a workflow definition payload for Xians Server upload.

    This function converts internal SDK models (AgentDefinition, WorkflowDefinition)
    into the JSON structure expected by the Xians Server API endpoint:
    POST /api/agent/definitions

    The server expects:
    - camelCase field names (e.g., workflowType, systemScoped)
    - Required fields: agent, workflowType, name, systemScoped, workers
    - Optional fields: description, activityDefinitions, workflowParameterDefinitions, hash

    Args:
        agent: The agent definition containing system_scoped flag.
        workflow: The workflow definition to upload.

    Returns:
        Dictionary with camelCase keys ready for JSON serialization.

    Example output:
        {
            "agent": "MyAgent",
            "workflowType": "MyAgent:BuiltIn Workflow-Conversational",
            "name": "Conversational",
            "systemScoped": false,
            "workers": 1,
            "description": "A conversational workflow",
            "hash": "abc123..."
        }
    """
    # Build workflow type identifier
    # Format: "{agent_key}:BuiltIn Workflow-{workflow_type_value}"
    agent_key = workflow.agent_key or agent.agent_key or agent.name
    workflow_type_str = f"{agent_key}:BuiltIn Workflow-{workflow.workflow_type.value}"

    # Create payload using the Pydantic model with camelCase serialization
    payload_model = WorkflowDefinitionPayload(
        agent=agent_key,
        workflow_type=workflow_type_str,
        name=workflow.name,
        system_scoped=agent.system_scoped,
        workers=workflow.workers,
        description=workflow.metadata.get("description") if workflow.metadata else None,
        hash=workflow.hash,
        version=workflow.version,
        metadata=workflow.metadata if workflow.metadata else {},
    )

    # Convert to dict with camelCase keys, excluding None values
    payload = payload_model.model_dump_camelcase()

    logger.debug(
        f"Built workflow definition payload for agent='{agent_key}', "
        f"workflow='{workflow.name}', type='{workflow_type_str}'"
    )

    return payload


__all__ = ["build_workflow_definition_payload"]

