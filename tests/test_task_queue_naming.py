"""Tests for task queue naming utilities."""

from xians.temporal_workflows.v1 import build_task_queue_name


class TestTaskQueueNaming:
    """Test suite for task queue naming logic."""

    def test_basic_task_queue_name(self) -> None:
        """Test basic task queue name generation."""
        name = build_task_queue_name(
            agent_key="my-agent",
            workflow_name="InvokeAgent",
        )

        assert name == "xians-default-user-my-agent-InvokeAgent"

    def test_system_scoped_task_queue(self) -> None:
        """Test system-scoped task queue name."""
        name = build_task_queue_name(
            agent_key="system-agent",
            workflow_name="Conversation",
            system_scoped=True,
        )

        assert name == "xians-default-system-system-agent-Conversation"

    def test_tenant_specific_task_queue(self) -> None:
        """Test tenant-specific task queue name."""
        name = build_task_queue_name(
            agent_key="tenant-agent",
            workflow_name="InvokeAgent",
            tenant_id="tenant-123",
        )

        assert name == "xians-tenant-123-user-tenant-agent-InvokeAgent"

    def test_full_task_queue_name(self) -> None:
        """Test task queue name with all parameters."""
        name = build_task_queue_name(
            agent_key="my-agent",
            workflow_name="Conversation",
            tenant_id="acme-corp",
            system_scoped=False,
        )

        assert name == "xians-acme-corp-user-my-agent-Conversation"

    def test_task_queue_name_deterministic(self) -> None:
        """Test that task queue names are deterministic."""
        name1 = build_task_queue_name(
            agent_key="agent-1",
            workflow_name="Test",
            tenant_id="tenant-a",
            system_scoped=True,
        )
        name2 = build_task_queue_name(
            agent_key="agent-1",
            workflow_name="Test",
            tenant_id="tenant-a",
            system_scoped=True,
        )

        assert name1 == name2

    def test_different_params_different_queues(self) -> None:
        """Test that different parameters produce different queue names."""
        name1 = build_task_queue_name("agent-1", "Workflow1")
        name2 = build_task_queue_name("agent-2", "Workflow1")
        name3 = build_task_queue_name("agent-1", "Workflow2")

        assert name1 != name2
        assert name1 != name3
        assert name2 != name3

