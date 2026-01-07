"""Tests for payload builder utility functions."""

import pytest

from xians.constants.v1.core import WorkflowType
from xians.models.v1.entities import AgentDefinition, WorkflowDefinition
from xians.utils.v1.payload_builder import build_workflow_definition_payload


class TestBuildWorkflowDefinitionPayload:
    """Test build_workflow_definition_payload function."""

    def test_basic_workflow_payload(self) -> None:
        """Test building a basic workflow definition payload."""
        agent = AgentDefinition(
            name="TestAgent",
            system_scoped=False,
            agent_key="TestAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="Conversational",
            workers=1,
            agent_key="TestAgent",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        # Verify required fields with camelCase keys
        assert payload["agent"] == "TestAgent"
        assert payload["workflowType"] == "TestAgent:BuiltIn Workflow-Conversational"
        assert payload["name"] == "Conversational"
        assert payload["systemScoped"] is False
        assert payload["workers"] == 1

    def test_system_scoped_agent(self) -> None:
        """Test that system_scoped flag is correctly transferred."""
        agent = AgentDefinition(
            name="SystemAgent",
            system_scoped=True,
            agent_key="SystemAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.TASK_BASED,
            name="InvokeAgent",
            workers=2,
            agent_key="SystemAgent",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        assert payload["systemScoped"] is True
        assert payload["workflowType"] == "SystemAgent:BuiltIn Workflow-TaskBased"

    def test_workflow_type_formatting(self) -> None:
        """Test that workflow type is formatted correctly."""
        agent = AgentDefinition(
            name="MyAgent",
            system_scoped=False,
            agent_key="MyAgent",
        )

        test_cases = [
            (WorkflowType.CONVERSATIONAL, "MyAgent:BuiltIn Workflow-Conversational"),
            (WorkflowType.TASK_BASED, "MyAgent:BuiltIn Workflow-TaskBased"),
            (WorkflowType.REACTIVE, "MyAgent:BuiltIn Workflow-Reactive"),
            (WorkflowType.CUSTOM, "MyAgent:BuiltIn Workflow-Custom"),
        ]

        for workflow_type, expected_type_str in test_cases:
            workflow = WorkflowDefinition(
                workflow_type=workflow_type,
                name="TestWorkflow",
                workers=1,
                agent_key="MyAgent",
            )

            payload = build_workflow_definition_payload(agent, workflow)
            assert payload["workflowType"] == expected_type_str

    def test_multiple_workers(self) -> None:
        """Test that workers count is correctly transferred."""
        agent = AgentDefinition(
            name="WorkerAgent",
            system_scoped=False,
            agent_key="WorkerAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="MultiWorker",
            workers=5,
            agent_key="WorkerAgent",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        assert payload["workers"] == 5
        assert isinstance(payload["workers"], int)

    def test_workflow_with_hash(self) -> None:
        """Test that workflow hash is included when present."""
        agent = AgentDefinition(
            name="HashAgent",
            system_scoped=False,
            agent_key="HashAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="HashedWorkflow",
            workers=1,
            agent_key="HashAgent",
            hash="abc123def456",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        assert payload["hash"] == "abc123def456"

    def test_workflow_with_version(self) -> None:
        """Test that workflow version is included."""
        agent = AgentDefinition(
            name="VersionAgent",
            system_scoped=False,
            agent_key="VersionAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="VersionedWorkflow",
            workers=1,
            agent_key="VersionAgent",
            version="2.1.0",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        assert payload["version"] == "2.1.0"

    def test_workflow_with_metadata_description(self) -> None:
        """Test that description from metadata is extracted."""
        agent = AgentDefinition(
            name="DescAgent",
            system_scoped=False,
            agent_key="DescAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="DescribedWorkflow",
            workers=1,
            agent_key="DescAgent",
            metadata={"description": "A workflow with a description"},
        )

        payload = build_workflow_definition_payload(agent, workflow)

        assert payload["description"] == "A workflow with a description"

    def test_agent_key_fallback(self) -> None:
        """Test that agent_key falls back to agent name if not set."""
        agent = AgentDefinition(
            name="FallbackAgent",
            system_scoped=False,
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="FallbackWorkflow",
            workers=1,
        )

        payload = build_workflow_definition_payload(agent, workflow)

        assert payload["agent"] == "FallbackAgent"
        assert "FallbackAgent:BuiltIn Workflow-" in payload["workflowType"]

    def test_payload_keys_are_camelcase(self) -> None:
        """Test that all payload keys use camelCase."""
        agent = AgentDefinition(
            name="CamelAgent",
            system_scoped=True,
            agent_key="CamelAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="CamelWorkflow",
            workers=3,
            agent_key="CamelAgent",
            hash="test123",
            version="1.0.0",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        # Check that snake_case keys are NOT present
        assert "workflow_type" not in payload
        assert "system_scoped" not in payload
        assert "agent_key" not in payload

        # Check that camelCase keys ARE present
        assert "workflowType" in payload
        assert "systemScoped" in payload
        assert "agent" in payload

    def test_no_null_values_for_required_fields(self) -> None:
        """Test that required fields are never null."""
        agent = AgentDefinition(
            name="RequiredAgent",
            system_scoped=False,
            agent_key="RequiredAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="RequiredWorkflow",
            workers=1,
            agent_key="RequiredAgent",
        )

        payload = build_workflow_definition_payload(agent, workflow)

        # Required fields must be present and not None
        assert payload["agent"] is not None
        assert payload["workflowType"] is not None
        assert payload["name"] is not None
        assert payload["systemScoped"] is not None
        assert payload["workers"] is not None

        # Optional fields should not be present if None
        # (they're excluded by model_dump_camelcase)

