"""Tests for definition hashing and serialization."""

import json

import pytest

from src.models.v1.entities import AgentDefinition, WorkflowDefinition
from src.utils.v1.hashing import compute_hash


class TestDefinitionHashing:
    """Test suite for definition hashing logic."""

    def test_compute_hash_deterministic(self) -> None:
        """Test that compute_hash produces deterministic results."""
        content = "test content"
        hash1 = compute_hash(content)
        hash2 = compute_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_compute_hash_different_inputs(self) -> None:
        """Test that different inputs produce different hashes."""
        hash1 = compute_hash("content1")
        hash2 = compute_hash("content2")

        assert hash1 != hash2

    def test_agent_definition_hash(self) -> None:
        """Test agent definition hashing for idempotency."""
        definition = AgentDefinition(
            name="test-agent",
            description="Test description",
            system_scoped=False,
        )

        # Compute hash from serialized content (excluding hash and agent_key)
        content = definition.model_dump_json(exclude={"hash", "agent_key"})
        hash1 = compute_hash(content)

        # Create identical definition
        definition2 = AgentDefinition(
            name="test-agent",
            description="Test description",
            system_scoped=False,
        )
        content2 = definition2.model_dump_json(exclude={"hash", "agent_key"})
        hash2 = compute_hash(content2)

        # Hashes should match
        assert hash1 == hash2

    def test_agent_definition_different_content_different_hash(self) -> None:
        """Test that different agent definitions produce different hashes."""
        def1 = AgentDefinition(name="agent1", description="Desc 1")
        def2 = AgentDefinition(name="agent1", description="Desc 2")

        content1 = def1.model_dump_json(exclude={"hash", "agent_key"})
        content2 = def2.model_dump_json(exclude={"hash", "agent_key"})

        hash1 = compute_hash(content1)
        hash2 = compute_hash(content2)

        assert hash1 != hash2

    def test_workflow_definition_hash(self) -> None:
        """Test workflow definition hashing."""
        from src.constants.v1.core import WorkflowType

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="ConversationWorkflow",
            workers=2,
            agent_key="test-agent",
        )

        content = workflow.model_dump_json(exclude={"hash"})
        hash_value = compute_hash(content)

        assert len(hash_value) == 64
        assert hash_value.isalnum()

    def test_workflow_definition_serialization(self) -> None:
        """Test workflow definition can be serialized to JSON."""
        from src.constants.v1.core import WorkflowType

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.TASK_BASED,
            name="InvokeWorkflow",
            workers=1,
            agent_key="my-agent",
            task_queue="my-queue",
            activity_name="my_activity",
        )

        json_str = workflow.model_dump_json()
        data = json.loads(json_str)

        assert data["workflow_type"] == "TaskBased"
        assert data["name"] == "InvokeWorkflow"
        assert data["workers"] == 1
        assert data["agent_key"] == "my-agent"
        assert data["task_queue"] == "my-queue"
        assert data["activity_name"] == "my_activity"

    def test_agent_definition_validation(self) -> None:
        """Test agent definition validation."""
        # Empty name should fail
        with pytest.raises(ValueError):
            AgentDefinition(name="")

        # Whitespace-only name should fail
        with pytest.raises(ValueError):
            AgentDefinition(name="   ")

        # Valid name should succeed
        definition = AgentDefinition(name="valid-agent")
        assert definition.name == "valid-agent"

