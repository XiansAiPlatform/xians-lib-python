"""Tests for XiansContext.CurrentAgent / CurrentWorkflow (property-style access)."""

import pytest

from xians.agents.core import XiansContext
from xians.interfaces.v1.platform import AgentRegistration, XiansWorkflow
from xians.models.v1.entities import XiansAgentRegistration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(name: str = "TestAgent") -> AgentRegistration:
    reg = XiansAgentRegistration(
        name=name,
        is_template=False,
        description="desc",
        summary=None,
        version=None,
        author=None,
        category=None,
    )
    return AgentRegistration(registration=reg, tenant_id="t1", platform=None)  # type: ignore[arg-type]


def _make_workflow(agent_name: str = "TestAgent", wf_name: str = "Conversational") -> XiansWorkflow:
    return XiansWorkflow(
        agent_name=agent_name,
        workflow_type=f"{agent_name}:{wf_name}",
        workflow_name=wf_name,
        workers=1,
        system_scoped=False,
        tenant_id="t1",
    )


@pytest.fixture(autouse=True)
def _clean_context():
    """Ensure every test starts and ends with a clean XiansContext."""
    XiansContext.clear()
    yield
    XiansContext.clear()


# ---------------------------------------------------------------------------
# CurrentAgent property tests
# ---------------------------------------------------------------------------

class TestCurrentAgent:
    """Tests for XiansContext.CurrentAgent (no parentheses)."""

    def test_resolves_from_workflow_context(self) -> None:
        """CurrentAgent resolves via agent name derived from workflow type + registry."""
        agent = _make_agent()
        XiansContext.register_agent("TestAgent", agent)

        XiansContext.set_workflow_type("TestAgent:Conversational")

        resolved = XiansContext.CurrentAgent

        assert resolved is agent
        assert resolved.name == "TestAgent"

    def test_resolves_from_workflow_id_when_type_not_set(self) -> None:
        """CurrentAgent derives agent name from workflow ID when type is not explicit."""
        agent = _make_agent()
        XiansContext.register_agent("TestAgent", agent)

        XiansContext.set_workflow_id("t1:TestAgent:Conversational:thread-1")

        resolved = XiansContext.CurrentAgent

        assert resolved is agent

    def test_explicit_agent_name_takes_priority(self) -> None:
        """Explicit set_agent_name() wins over workflow-type derivation."""
        agent_a = _make_agent("AgentA")
        agent_b = _make_agent("AgentB")
        XiansContext.register_agent("AgentA", agent_a)
        XiansContext.register_agent("AgentB", agent_b)

        XiansContext.set_workflow_type("AgentA:Workflow")
        XiansContext.set_agent_name("AgentB")

        assert XiansContext.CurrentAgent is agent_b

    def test_test_override_takes_precedence(self) -> None:
        """set_current_agent_for_tests wins over everything else."""
        real_agent = _make_agent()
        XiansContext.register_agent("TestAgent", real_agent)
        XiansContext.set_workflow_type("TestAgent:Conversational")

        class FakeAgent:
            name = "Fake"

        fake = FakeAgent()
        XiansContext.set_current_agent_for_tests(fake)

        assert XiansContext.CurrentAgent is fake
        assert XiansContext.CurrentAgent.name == "Fake"

        XiansContext.clear_current_agent_for_tests()

        assert XiansContext.CurrentAgent is real_agent

    def test_raises_runtime_error_when_no_context(self) -> None:
        """CurrentAgent raises RuntimeError when no identity is set."""
        with pytest.raises(RuntimeError, match="CurrentAgent is not available"):
            _ = XiansContext.CurrentAgent

    def test_raises_key_error_when_agent_not_registered(self) -> None:
        """CurrentAgent raises KeyError when agent name resolves but is not in registry."""
        XiansContext.set_agent_name("MissingAgent")

        with pytest.raises(KeyError, match="MissingAgent"):
            _ = XiansContext.CurrentAgent


# ---------------------------------------------------------------------------
# CurrentWorkflow property tests
# ---------------------------------------------------------------------------

class TestCurrentWorkflow:
    """Tests for XiansContext.CurrentWorkflow (no parentheses)."""

    def test_resolves_from_explicit_workflow_type(self) -> None:
        """CurrentWorkflow resolves from set_workflow_type + registry."""
        wf = _make_workflow()
        XiansContext.register_workflow("TestAgent:Conversational", wf)
        XiansContext.set_workflow_type("TestAgent:Conversational")

        resolved = XiansContext.CurrentWorkflow

        assert resolved is wf
        assert resolved.workflow_type == "TestAgent:Conversational"

    def test_resolves_from_workflow_id(self) -> None:
        """CurrentWorkflow derives type from workflow ID when not explicitly set."""
        wf = _make_workflow()
        XiansContext.register_workflow("TestAgent:Conversational", wf)
        XiansContext.set_workflow_id("t1:TestAgent:Conversational:thread-1")

        assert XiansContext.CurrentWorkflow is wf

    def test_raises_runtime_error_when_no_context(self) -> None:
        """CurrentWorkflow raises RuntimeError when no workflow identity is set."""
        with pytest.raises(RuntimeError, match="CurrentWorkflow is not available"):
            _ = XiansContext.CurrentWorkflow

    def test_raises_key_error_when_workflow_not_registered(self) -> None:
        """CurrentWorkflow raises KeyError when type resolves but is not in registry."""
        XiansContext.set_workflow_type("Missing:Workflow")

        with pytest.raises(KeyError, match="Missing:Workflow"):
            _ = XiansContext.CurrentWorkflow


# ---------------------------------------------------------------------------
# Combined agent + workflow test (end-to-end)
# ---------------------------------------------------------------------------

class TestCurrentAgentAndWorkflowTogether:
    """Simulate full activity context population and verify both resolve."""

    def test_full_activity_context(self) -> None:
        agent = _make_agent()
        wf = _make_workflow()
        XiansContext.register_agent("TestAgent", agent)
        XiansContext.register_workflow("TestAgent:Conversational", wf)

        XiansContext.set_workflow_id("t1:TestAgent:Conversational:thread-1")
        XiansContext.set_workflow_type("TestAgent:Conversational")
        XiansContext.set_agent_name("TestAgent")
        XiansContext.set_tenant_id("t1")
        XiansContext.set_participant_id("user-1")

        assert XiansContext.CurrentAgent is agent
        assert XiansContext.CurrentWorkflow is wf
        assert XiansContext.get_tenant_id() == "t1"
        assert XiansContext.get_participant_id() == "user-1"

    def test_context_cleared_after_clear(self) -> None:
        """After clear(), both properties raise."""
        agent = _make_agent()
        wf = _make_workflow()
        XiansContext.register_agent("TestAgent", agent)
        XiansContext.register_workflow("TestAgent:Conversational", wf)
        XiansContext.set_workflow_type("TestAgent:Conversational")
        XiansContext.set_agent_name("TestAgent")

        assert XiansContext.CurrentAgent is agent

        XiansContext.clear()

        with pytest.raises(RuntimeError):
            _ = XiansContext.CurrentAgent

        with pytest.raises(RuntimeError):
            _ = XiansContext.CurrentWorkflow


# ---------------------------------------------------------------------------
# ParticipantId (userId) resolution — C# parity tests
# ---------------------------------------------------------------------------

class TestParticipantIdResolution:
    """Mirror C# ``GetParticipantId`` / ``SafeParticipantId`` behavior.

    C# resolution order:
      1. AsyncLocal contextvar (``SetParticipantId`` / message-processing).
      2. ``Workflow.TypedSearchAttributes[userId]`` — only in workflow ctx.
      3. ``Workflow.Memo[userId]`` — only in workflow ctx.
      4. Throw (``GetParticipantId``) or return null (``SafeParticipantId``).
    ``SafeParticipantId`` additionally gates on ``InWorkflowOrActivity``.
    """

    def test_get_participant_id_prefers_contextvar(self) -> None:
        XiansContext.set_participant_id("user-1")
        assert XiansContext.get_participant_id() == "user-1"

    def test_get_participant_id_returns_none_when_no_source(self) -> None:
        # Python diverges from C# here — C# throws, Python returns None to
        # match the permissive Optional[str] return type used across the
        # module. safe_participant_id is the strict entry point.
        assert XiansContext.get_participant_id() is None

    def test_safe_participant_id_returns_none_outside_workflow_or_activity(
        self,
    ) -> None:
        """Matches C# ``SafeParticipantId`` which returns null when
        ``InWorkflowOrActivity`` is false — even if a contextvar was set.
        """
        XiansContext.set_participant_id("user-1")
        assert XiansContext.safe_participant_id() is None

    def test_safe_participant_id_returns_contextvar_in_activity(self) -> None:
        """Inside activity context, contextvar value is returned."""
        import sys
        import types
        from unittest.mock import patch

        temporalio = sys.modules.get("temporalio")
        if temporalio is None:  # pragma: no cover
            pytest.skip("temporalio package not available")

        fake_info = types.SimpleNamespace(
            workflow_id="t1:TestAgent:Conversational:thread-1",
            workflow_run_id="run-1",
        )
        with patch(
            "temporalio.activity.info", return_value=fake_info, create=True
        ):
            XiansContext.set_participant_id("user-from-ctx")
            assert XiansContext.safe_participant_id() == "user-from-ctx"

    def test_get_participant_id_falls_back_to_workflow_search_attrs(
        self,
    ) -> None:
        """Inside workflow context, when contextvar is empty, read from
        ``workflow.info().typed_search_attributes`` — matches C#
        ``GetFromSearchAttributes``.
        """
        import sys
        import types
        from unittest.mock import patch

        temporalio = sys.modules.get("temporalio")
        if temporalio is None:  # pragma: no cover
            pytest.skip("temporalio package not available")

        from temporalio.common import (
            SearchAttributeKey,
            SearchAttributePair,
            TypedSearchAttributes,
        )

        attrs = TypedSearchAttributes(
            search_attributes=[
                SearchAttributePair(
                    SearchAttributeKey.for_keyword("userId"), "user-sa"
                ),
            ]
        )
        fake_info = types.SimpleNamespace(typed_search_attributes=attrs)

        # Patch activity.info to fail (so the attribute lookup thinks we are
        # NOT in an activity), and patch workflow.info to return fake_info.
        with patch(
            "temporalio.workflow.info", return_value=fake_info, create=True
        ):
            # No contextvar set → falls back to search attributes.
            assert XiansContext.get_participant_id() == "user-sa"

    def test_get_participant_id_falls_back_to_workflow_memo(self) -> None:
        """Inside workflow context, when search attrs lack ``userId``, read
        from the memo dict — matches C# ``GetFromWorkflowMemo``.
        """
        import sys
        import types
        from unittest.mock import patch

        temporalio = sys.modules.get("temporalio")
        if temporalio is None:  # pragma: no cover
            pytest.skip("temporalio package not available")

        from temporalio.common import TypedSearchAttributes

        empty_attrs = TypedSearchAttributes(search_attributes=[])
        fake_info = types.SimpleNamespace(typed_search_attributes=empty_attrs)

        with patch(
            "temporalio.workflow.info", return_value=fake_info, create=True
        ), patch(
            "temporalio.workflow.memo",
            return_value={"userId": "user-memo"},
            create=True,
        ):
            assert XiansContext.get_participant_id() == "user-memo"
