"""Payload models for Xians Server API requests with camelCase serialization."""

from typing import Any

from pydantic import BaseModel, Field


class ParameterDefinitionPayload(BaseModel):
    """
    Represents a parameter definition in camelCase format for API requests.

    Attributes:
        name: Parameter name.
        type: Parameter type (e.g., 'string', 'integer', 'boolean').
        required: Whether the parameter is required.
        default_value: Optional default value for the parameter.
        description: Optional description of the parameter.
    """

    name: str = Field(description="Parameter name", serialization_alias="name")
    type: str = Field(description="Parameter type", serialization_alias="type")
    required: bool = Field(default=True, description="Whether parameter is required", serialization_alias="required")
    default_value: Any | None = Field(default=None, description="Default value", serialization_alias="defaultValue")
    description: str | None = Field(default=None, description="Parameter description", serialization_alias="description")

    model_config = {"populate_by_name": True}


class ActivityDefinitionPayload(BaseModel):
    """
    Represents an activity definition in camelCase format for API requests.

    Attributes:
        name: Activity name.
        description: Optional activity description.
        parameters: List of parameter definitions.
    """

    name: str = Field(description="Activity name", serialization_alias="name")
    description: str | None = Field(default=None, description="Activity description", serialization_alias="description")
    parameters: list[ParameterDefinitionPayload] = Field(
        default_factory=list,
        description="Activity parameters",
        serialization_alias="parameters",
    )

    model_config = {"populate_by_name": True}


class WorkflowDefinitionPayload(BaseModel):
    """
    Payload for uploading workflow definitions to Xians Server.

    This model ensures all field names are serialized to camelCase
    to match the server's expected JSON schema.

    Required fields (MUST NOT be null):
        agent: Agent name/key (non-empty string).
        workflow_type: Workflow type identifier (non-empty string).
        name: Workflow name (non-empty string).
        system_scoped: Whether the workflow is system-scoped (boolean).
        workers: Number of worker instances (integer >= 1).

    Optional fields:
        description: Workflow description.
        activity_definitions: List of activity definitions.
        workflow_parameter_definitions: List of workflow parameters.
        hash: Content hash for idempotency.
        version: Version string.
        metadata: Additional metadata.
    """

    agent: str = Field(
        min_length=1,
        description="Agent name/key (required, non-empty)",
        serialization_alias="agent",
    )
    workflow_type: str = Field(
        min_length=1,
        description="Workflow type identifier (required, non-empty)",
        serialization_alias="workflowType",
    )
    name: str = Field(
        min_length=1,
        description="Workflow name (required, non-empty)",
        serialization_alias="name",
    )
    system_scoped: bool = Field(
        description="Whether workflow is system-scoped (required boolean)",
        serialization_alias="systemScoped",
    )
    workers: int = Field(
        ge=1,
        description="Number of worker instances (required, >= 1)",
        serialization_alias="workers",
    )
    description: str | None = Field(
        default=None,
        description="Workflow description (optional)",
        serialization_alias="description",
    )
    activity_definitions: list[ActivityDefinitionPayload] = Field(
        default_factory=list,
        description="Activity definitions (optional)",
        serialization_alias="activityDefinitions",
    )
    workflow_parameter_definitions: list[ParameterDefinitionPayload] = Field(
        default_factory=list,
        description="Workflow parameter definitions (optional)",
        serialization_alias="workflowParameterDefinitions",
    )
    hash: str | None = Field(
        default=None,
        description="Content hash for idempotency (optional)",
        serialization_alias="hash",
    )
    version: str | None = Field(
        default=None,
        description="Version string (optional)",
        serialization_alias="version",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (optional)",
        serialization_alias="metadata",
    )

    model_config = {"populate_by_name": True}

    def model_dump_camelcase(self, **kwargs: Any) -> dict[str, Any]:
        """
        Dump model to dict with camelCase keys, excluding None values for optional fields.

        This ensures the payload sent to the server:
        1. Uses camelCase for all keys
        2. Does not include null values for optional fields
        3. Always includes required fields (even if they have defaults)
        4. Excludes empty lists/dicts for optional collection fields
        """
        data = self.model_dump(by_alias=True, exclude_none=True, **kwargs)

        # Remove empty collections for optional fields
        optional_collection_fields = ["activityDefinitions", "workflowParameterDefinitions", "metadata"]
        for field in optional_collection_fields:
            if field in data and not data[field]:
                del data[field]

        return data


__all__ = [
    "ParameterDefinitionPayload",
    "ActivityDefinitionPayload",
    "WorkflowDefinitionPayload",
]

