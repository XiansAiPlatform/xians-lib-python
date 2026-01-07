"""Tests for Xians Server API payload models and camelCase serialization."""

import pytest
from pydantic import ValidationError

from xians.models.v1.payloads import (
    ActivityDefinitionPayload,
    ParameterDefinitionPayload,
    WorkflowDefinitionPayload,
)


class TestParameterDefinitionPayload:
    """Test ParameterDefinitionPayload camelCase serialization."""

    def test_camelcase_serialization(self) -> None:
        """Test that parameter definitions serialize to camelCase."""
        param = ParameterDefinitionPayload(
            name="my_param",
            type="string",
            required=False,
            default_value="test",
            description="A test parameter",
        )

        data = param.model_dump(by_alias=True)

        assert data["name"] == "my_param"
        assert data["type"] == "string"
        assert data["required"] is False
        assert data["defaultValue"] == "test"  # camelCase
        assert data["description"] == "A test parameter"


class TestActivityDefinitionPayload:
    """Test ActivityDefinitionPayload camelCase serialization."""

    def test_camelcase_serialization(self) -> None:
        """Test that activity definitions serialize to camelCase."""
        param = ParameterDefinitionPayload(
            name="input_text",
            type="string",
            required=True,
        )

        activity = ActivityDefinitionPayload(
            name="process_text",
            description="Process text input",
            parameters=[param],
        )

        data = activity.model_dump(by_alias=True)

        assert data["name"] == "process_text"
        assert data["description"] == "Process text input"
        assert len(data["parameters"]) == 1
        assert data["parameters"][0]["name"] == "input_text"


class TestWorkflowDefinitionPayload:
    """Test WorkflowDefinitionPayload camelCase serialization and validation."""

    def test_minimal_valid_payload(self) -> None:
        """Test minimal valid payload with required fields only."""
        payload = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="MyAgent:BuiltIn Workflow-Conversational",
            name="Conversational",
            system_scoped=False,
            workers=1,
        )

        data = payload.model_dump_camelcase()

        # Required fields with camelCase keys
        assert data["agent"] == "MyAgent"
        assert data["workflowType"] == "MyAgent:BuiltIn Workflow-Conversational"
        assert data["name"] == "Conversational"
        assert data["systemScoped"] is False
        assert data["workers"] == 1

        # Optional fields should not be present when None
        assert "description" not in data
        assert "hash" not in data

    def test_full_payload_with_optional_fields(self) -> None:
        """Test payload with all optional fields populated."""
        payload = WorkflowDefinitionPayload(
            agent="TestAgent",
            workflow_type="TestAgent:BuiltIn Workflow-TaskBased",
            name="TaskWorkflow",
            system_scoped=True,
            workers=3,
            description="A test workflow",
            hash="abc123def456",
            version="2.0.0",
            metadata={"key": "value"},
        )

        data = payload.model_dump_camelcase()

        assert data["agent"] == "TestAgent"
        assert data["workflowType"] == "TestAgent:BuiltIn Workflow-TaskBased"
        assert data["name"] == "TaskWorkflow"
        assert data["systemScoped"] is True
        assert data["workers"] == 3
        assert data["description"] == "A test workflow"
        assert data["hash"] == "abc123def456"
        assert data["version"] == "2.0.0"
        assert data["metadata"] == {"key": "value"}

    def test_workers_must_be_integer_not_string(self) -> None:
        """Test that workers field is validated as integer."""
        payload = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="MyAgent:BuiltIn Workflow-Conversational",
            name="Conversational",
            system_scoped=False,
            workers=2,
        )

        data = payload.model_dump_camelcase()
        assert isinstance(data["workers"], int)
        assert data["workers"] == 2

    def test_validation_agent_empty_string(self) -> None:
        """Test that agent field cannot be empty string."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowDefinitionPayload(
                agent="",
                workflow_type="Type",
                name="Name",
                system_scoped=False,
                workers=1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("agent",) for e in errors)

    def test_validation_workflow_type_empty_string(self) -> None:
        """Test that workflow_type field cannot be empty string."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowDefinitionPayload(
                agent="MyAgent",
                workflow_type="",
                name="Name",
                system_scoped=False,
                workers=1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("workflow_type",) for e in errors)

    def test_validation_name_empty_string(self) -> None:
        """Test that name field cannot be empty string."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowDefinitionPayload(
                agent="MyAgent",
                workflow_type="Type",
                name="",
                system_scoped=False,
                workers=1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_validation_workers_less_than_one(self) -> None:
        """Test that workers field must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowDefinitionPayload(
                agent="MyAgent",
                workflow_type="Type",
                name="Name",
                system_scoped=False,
                workers=0,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("workers",) for e in errors)

    def test_system_scoped_is_boolean(self) -> None:
        """Test that system_scoped field is validated as boolean."""
        payload_false = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="Type",
            name="Name",
            system_scoped=False,
            workers=1,
        )

        payload_true = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="Type",
            name="Name",
            system_scoped=True,
            workers=1,
        )

        data_false = payload_false.model_dump_camelcase()
        data_true = payload_true.model_dump_camelcase()

        assert data_false["systemScoped"] is False
        assert data_true["systemScoped"] is True

    def test_example_payload_from_requirements(self) -> None:
        """Test the example payload from the requirements."""
        payload = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="MyAgent:BuiltIn Workflow-Conversational",
            name="Conversational",
            system_scoped=False,
            workers=1,
        )

        data = payload.model_dump_camelcase()

        expected = {
            "agent": "MyAgent",
            "workflowType": "MyAgent:BuiltIn Workflow-Conversational",
            "name": "Conversational",
            "systemScoped": False,
            "workers": 1,
        }

        assert data == expected

    def test_metadata_defaults_to_empty_dict_but_excluded_when_empty(self) -> None:
        """Test that empty metadata dict is excluded from serialization."""
        payload = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="Type",
            name="Name",
            system_scoped=False,
            workers=1,
        )

        data = payload.model_dump_camelcase()

        # Empty metadata should not be in the output
        assert "metadata" not in data or data["metadata"] == {}

    def test_activity_definitions_serialization(self) -> None:
        """Test that activityDefinitions serializes correctly."""
        activity = ActivityDefinitionPayload(
            name="my_activity",
            description="Test activity",
        )

        payload = WorkflowDefinitionPayload(
            agent="MyAgent",
            workflow_type="Type",
            name="Name",
            system_scoped=False,
            workers=1,
            activity_definitions=[activity],
        )

        data = payload.model_dump_camelcase()

        assert "activityDefinitions" in data
        assert len(data["activityDefinitions"]) == 1
        assert data["activityDefinitions"][0]["name"] == "my_activity"

