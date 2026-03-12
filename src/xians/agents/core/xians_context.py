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

_agent_registry: dict[str, object] = {}
_workflow_registry: dict[str, object] = {}


class XiansContext:
    """Static context manager matching C# XiansContext.

    Uses Python's contextvars for async-safe per-task storage.
    Provides agent/workflow registration and lookup.
    """

    @staticmethod
    def get_tenant_id() -> Optional[str]:
        return _current_tenant_id.get()

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

    @staticmethod
    def set_request_id(value: Optional[str]) -> None:
        _current_request_id.set(value)

    @staticmethod
    def get_id_postfix() -> Optional[str]:
        return _current_id_postfix.get()

    @staticmethod
    def set_id_postfix(value: Optional[str]) -> None:
        _current_id_postfix.set(value)

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

    @staticmethod
    def clear() -> None:
        _agent_registry.clear()
        _workflow_registry.clear()
        _current_tenant_id.set(None)
        _current_participant_id.set(None)
        _current_authorization.set(None)
        _current_request_id.set(None)
        _current_id_postfix.set(None)
