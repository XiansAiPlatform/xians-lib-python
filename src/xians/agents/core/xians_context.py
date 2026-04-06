"""XiansContext - async context propagation via contextvars. Matches C# XiansContext."""

import contextvars
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass

_current_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_tenant_id", default=None
)
_current_participant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_participant_id", default=None
)
_current_authorization: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_authorization", default=None
)
_current_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_request_id", default=None
)
_current_id_postfix: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_id_postfix", default=None
)

_current_workflow_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_workflow_id", default=None
)
_current_workflow_type: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_workflow_type", default=None
)
_current_agent_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "xians_agent_name", default=None
)

_current_agent_override: contextvars.ContextVar[Optional[object]] = (
    contextvars.ContextVar("xians_current_agent_override", default=None)
)
_static_current_agent_override: Optional[object] = None

_agent_registry: dict[str, object] = {}
_workflow_registry: dict[str, object] = {}


# ---------------------------------------------------------------------------
# Metaclass that exposes CurrentAgent / CurrentWorkflow as class-level
# properties so they can be accessed without parentheses, mirroring C#:
#
#   XiansContext.CurrentAgent.name
#   XiansContext.CurrentWorkflow.workflow_type
# ---------------------------------------------------------------------------

class _XiansContextMeta(type):
    """Metaclass enabling property-style access on the XiansContext class itself."""

    @property
    def CurrentAgent(cls) -> object:
        """Resolve the current agent for this async context.

        Resolution order (mirrors C# XiansContext.CurrentAgent):
        1. Test override (async-local)
        2. Test override (static fallback for cross-async test scenarios)
        3. Agent name derived from workflow type / ID → registry lookup
        """
        override = _current_agent_override.get()
        if override is not None:
            return override

        if _static_current_agent_override is not None:
            return _static_current_agent_override

        agent_name = cls._resolve_agent_name()
        if not agent_name:
            raise RuntimeError(
                "CurrentAgent is not available. No agent context is set. "
                "Ensure you are calling this from within a Temporal activity or "
                "have configured a test override via set_current_agent_for_tests()."
            )

        agent = _agent_registry.get(agent_name)
        if agent is None:
            raise KeyError(
                f"Agent '{agent_name}' not found in registry. "
                "Ensure the agent was registered via XiansPlatform.agents.register()."
            )

        return agent

    @property
    def CurrentWorkflow(cls) -> object:
        """Resolve the current workflow for this async context.

        Mirrors C# XiansContext.CurrentWorkflow: derives workflow type from
        context or workflow ID, then looks up the XiansWorkflow instance.
        """
        workflow_type = cls._resolve_workflow_type()
        if not workflow_type:
            raise RuntimeError(
                "CurrentWorkflow is not available. No workflow context is set. "
                "Ensure you are calling this from within a Temporal workflow or "
                "activity, with workflow identity populated."
            )

        workflow = _workflow_registry.get(workflow_type)
        if workflow is None:
            raise KeyError(
                f"Workflow '{workflow_type}' not found in registry. "
                "Ensure the workflow was defined via AgentRegistration.define_builtin_workflow() "
                "or define_custom_workflow()."
            )

        return workflow

    @property
    def Metrics(cls):
        """Access metrics for the current agent. Matches C# XiansContext.Metrics.

        Use from workflows/activities:
            await XiansContext.Metrics
                .with_metric("workflow", "started", 1, "count")
                .report_async()
        """
        return cls.CurrentAgent.metrics

    @property
    def Documents(cls):
        """Access document collection for the current agent. Matches C# XiansContext.Documents.

        Use from workflows/activities:
            doc = await XiansContext.Documents.save_async(document)
            result = await XiansContext.Documents.get_by_key_async("type", "key")
        """
        return cls.CurrentAgent.documents

    @property
    def Messaging(cls):
        """Access proactive messaging helper. Matches C# XiansContext.Messaging.

        Use from workflows/activities:
            await XiansContext.Messaging.send_chat_async("Hello!")
            await XiansContext.Messaging.send_data_async("Update", {"status": "done"})
        """
        from ..messaging.messaging_helper import MessagingHelper
        return MessagingHelper


class XiansContext(metaclass=_XiansContextMeta):
    """Central context hub for accessing all Xians SDK functionality.

    Matches C# XiansContext. Uses Python's contextvars for async-safe
    per-task storage.

    Key properties (accessed without parentheses, just like C#):
        XiansContext.CurrentAgent    — the agent for the current execution
        XiansContext.CurrentWorkflow — the workflow for the current execution
    """

    # ------------------------------------------------------------------
    # Tenant / participant / authorization / request context
    # ------------------------------------------------------------------

    @staticmethod
    def get_tenant_id() -> Optional[str]:
        """Get tenant ID from async-local context or workflow ID.

        Resolution order (mirrors C# XiansContext.GetTenantId):
        1. Explicit contextvar (_current_tenant_id)
        2. Extract from workflow ID (first segment before ':')
        """
        value = _current_tenant_id.get()
        if value:
            return value
        return XiansContext._extract_tenant_id_from_workflow_id()

    @staticmethod
    def set_tenant_id(value: Optional[str]) -> None:
        _current_tenant_id.set(value)

    @staticmethod
    def get_participant_id() -> Optional[str]:
        return _current_participant_id.get()

    @staticmethod
    def set_participant_id(value: Optional[str]) -> None:
        _current_participant_id.set(value)

    @staticmethod
    def get_authorization() -> Optional[str]:
        return _current_authorization.get()

    @staticmethod
    def set_authorization(value: Optional[str]) -> None:
        _current_authorization.set(value)

    @staticmethod
    def get_request_id() -> Optional[str]:
        return _current_request_id.get()

    # ------------------------------------------------------------------
    # Safe getters (never raise, return None if unavailable)
    # Mirrors C# XiansContext.SafeTenantId, SafeParticipantId, etc.
    # ------------------------------------------------------------------

    @staticmethod
    def safe_tenant_id() -> Optional[str]:
        """Safely get tenant ID without raising. Returns None if unavailable."""
        try:
            return _current_tenant_id.get() or XiansContext._extract_tenant_id_from_workflow_id()
        except Exception:
            return None

    @staticmethod
    def safe_participant_id() -> Optional[str]:
        """Safely get participant ID without raising. Returns None if unavailable."""
        try:
            return _current_participant_id.get()
        except Exception:
            return None

    @staticmethod
    def safe_workflow_id() -> Optional[str]:
        """Safely get workflow ID without raising. Returns None if unavailable."""
        try:
            return _current_workflow_id.get() or XiansContext._get_from_temporal_context("workflow_id")
        except Exception:
            return None

    @staticmethod
    def safe_workflow_type() -> Optional[str]:
        """Safely get workflow type without raising. Returns None if unavailable."""
        try:
            return XiansContext._resolve_workflow_type()
        except Exception:
            return None

    @staticmethod
    def safe_agent_name() -> Optional[str]:
        """Safely get agent name without raising. Returns None if unavailable."""
        try:
            return XiansContext._resolve_agent_name()
        except Exception:
            return None

    @staticmethod
    def safe_id_postfix() -> Optional[str]:
        """Safely get id postfix without raising. Returns None if unavailable."""
        try:
            return _current_id_postfix.get() or XiansContext._parse_id_postfix_from_workflow_id()
        except Exception:
            return None

    @staticmethod
    def set_request_id(value: Optional[str]) -> None:
        _current_request_id.set(value)

    @staticmethod
    def get_id_postfix() -> Optional[str]:
        """Get idPostfix from async-local context or workflow ID.

        Resolution order (mirrors C# XiansContext.GetIdPostfix):
        1. Explicit contextvar (_current_id_postfix)
        2. Parse from workflow ID (4th segment, stripped of Temporal timestamp suffix)
        """
        value = _current_id_postfix.get()
        if value:
            return value
        return XiansContext._parse_id_postfix_from_workflow_id()

    @staticmethod
    def set_id_postfix(value: Optional[str]) -> None:
        _current_id_postfix.set(value)

    # ------------------------------------------------------------------
    # Workflow / agent identity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def set_workflow_id(value: Optional[str]) -> None:
        _current_workflow_id.set(value)

    @staticmethod
    def get_workflow_id() -> Optional[str]:
        """Get workflow ID from explicit context or Temporal execution context.

        Mirrors C# XiansContext.GetWorkflowId -> WorkflowMetadataResolver.GetWorkflowId.
        """
        wf_id = _current_workflow_id.get()
        if wf_id:
            return wf_id
        return XiansContext._get_from_temporal_context("workflow_id")

    @staticmethod
    def set_workflow_type(value: Optional[str]) -> None:
        _current_workflow_type.set(value)

    @staticmethod
    def set_agent_name(value: Optional[str]) -> None:
        _current_agent_name.set(value)

    # ------------------------------------------------------------------
    # Temporal context helpers (mirrors C# GetFromContext / InWorkflowOrActivity)
    # ------------------------------------------------------------------

    @staticmethod
    def _try_get_from_temporal_activity(attr: str) -> Optional[str]:
        """Try reading an attribute from Temporal activity context.

        Mirrors C#: ActivityExecutionContext.Current.Info.<attr>
        """
        try:
            from temporalio import activity as _activity
            return getattr(_activity.info(), attr, None)
        except Exception:
            return None

    @staticmethod
    def _try_get_from_temporal_workflow(attr: str) -> Optional[str]:
        """Try reading an attribute from Temporal workflow context.

        Mirrors C#: Workflow.Info.<attr>
        """
        try:
            from temporalio import workflow as _workflow
            return getattr(_workflow.info(), attr, None)
        except Exception:
            return None

    @staticmethod
    def _get_from_temporal_context(attr: str) -> Optional[str]:
        """Try reading from Temporal activity context first, then workflow context.

        Mirrors C# GetFromContext(fromWorkflow, fromActivity).
        """
        value = XiansContext._try_get_from_temporal_activity(attr)
        if value:
            return value
        return XiansContext._try_get_from_temporal_workflow(attr)

    @staticmethod
    def in_activity() -> bool:
        """Check if currently executing inside a Temporal activity."""
        try:
            from temporalio import activity as _activity
            _activity.info()
            return True
        except Exception:
            return False

    @staticmethod
    def in_workflow() -> bool:
        """Check if currently executing inside a Temporal workflow."""
        try:
            from temporalio import workflow as _workflow
            _workflow.info()
            return True
        except Exception:
            return False

    @staticmethod
    def in_workflow_or_activity() -> bool:
        return XiansContext.in_activity() or XiansContext.in_workflow()

    # ------------------------------------------------------------------
    # Workflow ID parsing (mirrors C# TenantContext / WorkflowMetadataResolver)
    # ------------------------------------------------------------------

    _TEMPORAL_SCHEDULED_TIMESTAMP_RE = None

    @staticmethod
    def _extract_tenant_id_from_workflow_id() -> Optional[str]:
        """Extract tenant ID from the workflow ID (first segment before ':').

        Mirrors C# TenantContext.ExtractTenantId.
        Workflow ID format: {tenantId}:{agentName}:{workflowName}[:{idPostfix}]
        """
        workflow_id = XiansContext.get_workflow_id()
        if not workflow_id:
            return None
        parts = workflow_id.split(":")
        if len(parts) >= 2 and parts[0]:
            return parts[0]
        return None

    @staticmethod
    def _parse_id_postfix_from_workflow_id() -> Optional[str]:
        """Parse idPostfix from workflow ID (4th segment, stripped of Temporal timestamp suffix).

        Mirrors C# WorkflowMetadataResolver.ParseIdPostfixFromWorkflowId.
        Workflow ID format: {tenantId}:{agentName}:{workflowName}:{idPostfix}
        """
        import re

        workflow_id = XiansContext.get_workflow_id()
        if not workflow_id:
            return None
        parts = workflow_id.split(":")
        if len(parts) < 4:
            return None
        id_part = parts[3]
        if not id_part:
            return None

        if XiansContext._TEMPORAL_SCHEDULED_TIMESTAMP_RE is None:
            XiansContext._TEMPORAL_SCHEDULED_TIMESTAMP_RE = re.compile(
                r"(?:-\d{4}-\d{2}-\d{2}T[\d:.Z]+)+$"
            )
        stripped = XiansContext._TEMPORAL_SCHEDULED_TIMESTAMP_RE.sub("", id_part)
        return stripped if stripped else id_part

    # ------------------------------------------------------------------
    # Internal resolution helpers (used by metaclass properties)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_workflow_type() -> Optional[str]:
        """Resolve workflow type from explicit context, Temporal context, or workflow ID.

        Resolution order (mirrors C# XiansContext.GetWorkflowType):
        1. Explicit contextvar (_current_workflow_type)
        2. Temporal activity/workflow context (ActivityInfo.workflow_type / WorkflowInfo.workflow_type)
        3. Parse from workflow ID
        """
        workflow_type = _current_workflow_type.get()
        if workflow_type:
            return workflow_type

        temporal_wf_type = XiansContext._get_from_temporal_context("workflow_type")
        if temporal_wf_type:
            return temporal_wf_type

        workflow_id = _current_workflow_id.get()
        if not workflow_id:
            return None

        parts = workflow_id.split(":")
        if len(parts) >= 3:
            return f"{parts[1]}:{parts[2]}"

        return None

    @staticmethod
    def _resolve_agent_name() -> Optional[str]:
        """Resolve agent name from explicit context or workflow type.

        Resolution order (mirrors C# XiansContext.AgentName):
        1. Explicit contextvar (_current_agent_name)
        2. Derived from workflow type (first segment before ':')
        """
        agent_name = _current_agent_name.get()
        if agent_name:
            return agent_name

        workflow_type = XiansContext._resolve_workflow_type()
        if not workflow_type:
            return None

        if ":" in workflow_type:
            return workflow_type.split(":", 1)[0]

        return workflow_type

    # ------------------------------------------------------------------
    # Test helpers (mirror C# SetCurrentAgentForTests / ClearCurrentAgentForTests)
    # ------------------------------------------------------------------

    @staticmethod
    def set_current_agent_for_tests(agent: object) -> None:
        """Force ``CurrentAgent`` to return a specific agent in tests."""
        if agent is None:
            raise ValueError("agent cannot be None")

        global _static_current_agent_override
        _current_agent_override.set(agent)
        _static_current_agent_override = agent

    @staticmethod
    def clear_current_agent_for_tests() -> None:
        """Clear any test overrides for ``CurrentAgent``."""
        global _static_current_agent_override
        _current_agent_override.set(None)
        _static_current_agent_override = None

    # ------------------------------------------------------------------
    # Agent / workflow registry
    # ------------------------------------------------------------------

    @staticmethod
    def register_agent(name: str, agent: object) -> None:
        _agent_registry[name] = agent

    @staticmethod
    def get_agent(name: str) -> Optional[object]:
        return _agent_registry.get(name)

    @staticmethod
    def get_all_agents() -> list[object]:
        return list(_agent_registry.values())

    @staticmethod
    def register_workflow(workflow_type: str, workflow: object) -> None:
        _workflow_registry[workflow_type] = workflow

    @staticmethod
    def get_workflow(workflow_type: str) -> Optional[object]:
        return _workflow_registry.get(workflow_type)

    @staticmethod
    def get_all_workflows() -> list[object]:
        return list(_workflow_registry.values())

    # ------------------------------------------------------------------
    # Workflow identity construction
    # ------------------------------------------------------------------

    @staticmethod
    def build_workflow_type(agent_name: str, workflow_name: str) -> str:
        return f"{agent_name}:{workflow_name}"

    @staticmethod
    def build_workflow_id(
        tenant_id: str,
        agent_name: str,
        workflow_name: str,
        id_postfix: Optional[str] = None,
    ) -> str:
        base = f"{tenant_id}:{agent_name}:{workflow_name}"
        if id_postfix:
            return f"{base}:{id_postfix}"
        return base

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def clear() -> None:
        _agent_registry.clear()
        _workflow_registry.clear()
        _current_tenant_id.set(None)
        _current_participant_id.set(None)
        _current_authorization.set(None)
        _current_request_id.set(None)
        _current_id_postfix.set(None)
        _current_workflow_id.set(None)
        _current_workflow_type.set(None)
        _current_agent_name.set(None)
        _current_agent_override.set(None)
        global _static_current_agent_override
        _static_current_agent_override = None
