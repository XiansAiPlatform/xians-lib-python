"""Workflow log integration for ``ProcessAndSendMessage``.

Keeps ``message_activities.py`` close to upstream C# shape: all optional Auditing /
``POST /api/agent/logs`` behavior lives here so the activity class stays a thin
orchestrator (context + handler dispatch + webhook), with logging hooks calling
into this module.
"""

from __future__ import annotations

from temporalio import activity

from ...agents.core.xians_context import XiansContext
from ...agents.workflow_logs import WorkflowLogEmitter, WorkflowLogService, XiansLogger
from .models import ProcessMessageActivityRequest, WorkflowHandlerMetadata

logger = XiansLogger.for_name(__name__)


def temporal_workflow_id_for_logging(fallback: str | None) -> str:
    """Canonical Temporal instance id for ingest ``workflowId`` (.NET parity)."""
    try:
        wid = (activity.info().workflow_id or "").strip()
    except Exception:
        wid = ""
    if wid:
        return wid
    return (fallback or "").strip()


def temporal_workflow_run_id_for_logging(fallback: str | None) -> str | None:
    """Temporal run id for ``workflowRunId`` on ingest."""
    try:
        rid = (activity.info().workflow_run_id or "").strip()
    except Exception:
        rid = ""
    if rid:
        return rid
    fb = (fallback or "").strip()
    return fb or None


def apply_metadata_id_postfix(request: ProcessMessageActivityRequest) -> None:
    """Apply ``idPostfix`` from activity ``metadata`` (from workflow memo)."""
    if not request.metadata:
        return
    for key, val in request.metadata.items():
        if val is None:
            continue
        norm = str(key).lower().replace("-", "").replace("_", "")
        if norm == "idpostfix":
            s = str(val).strip()
            if s:
                XiansContext.set_id_postfix(s)
            return


def setup_message_activity_context(
    request: ProcessMessageActivityRequest,
    metadata: WorkflowHandlerMetadata,
) -> tuple[str, str | None, str, str | None]:
    """Populate ``XiansContext`` for handlers and log correlation.

    Uses canonical Temporal workflow id for context so ``safe_id_postfix()`` parses
    correctly; outbound APIs still use ``request.workflow_id`` via ``UserMessageContext``.

    Returns:
        ``(log_workflow_id, workflow_run_id, log_agent, log_participant)``
    """
    log_workflow_id = temporal_workflow_id_for_logging(request.workflow_id)
    workflow_run_id = temporal_workflow_run_id_for_logging(request.workflow_run_id)

    XiansContext.set_workflow_id(log_workflow_id)
    XiansContext.set_workflow_type(request.workflow_type)
    if request.workflow_type:
        agent_name = request.workflow_type.split(":", 1)[0]
    else:
        agent_name = None
    XiansContext.set_agent_name(agent_name)

    XiansContext.set_tenant_id(request.tenant_id)
    XiansContext.set_participant_id(request.participant_id)
    XiansContext.set_authorization(request.authorization)
    XiansContext.set_request_id(request.request_id)
    apply_metadata_id_postfix(request)

    log_agent = (metadata.agent_name or "").strip() or (agent_name or "")
    log_participant = (request.participant_id or "").strip() or None

    id_postfix = XiansContext.safe_id_postfix()
    logger.log_debug(
        f"Activity log context: workflowId={log_workflow_id} workflowType={request.workflow_type} "
        f"agent={log_agent} idPostfix={id_postfix} runId={workflow_run_id} participant={log_participant}"
    )

    return log_workflow_id, workflow_run_id, log_agent, log_participant


def try_create_workflow_log_emitter(
    workflow_logs_service: WorkflowLogService | None,
    request: ProcessMessageActivityRequest,
    *,
    log_workflow_id: str,
    workflow_run_id: str | None,
    log_agent: str,
    log_participant: str | None,
) -> WorkflowLogEmitter | None:
    """Return an emitter when server logging is configured and required fields exist."""
    if not workflow_logs_service or not log_workflow_id or not request.workflow_type or not log_agent:
        return None
    if not workflow_run_id:
        logger.log_debug(
            "WorkflowLogEmitter: workflow_run_id missing after Temporal lookup; "
            "emitting without workflowRunId"
        )
    try:
        return WorkflowLogEmitter(
            log_service=workflow_logs_service,
            agent=log_agent,
            workflow_type=request.workflow_type,
            workflow_id=log_workflow_id,
            workflow_run_id=workflow_run_id,
            activation=XiansContext.safe_id_postfix(),
            participant_id=log_participant,
            tenant_id=request.tenant_id or XiansContext.safe_tenant_id(),
        )
    except Exception:
        logger.log_warning("Failed to initialize WorkflowLogEmitter")
        return None


def teardown_message_activity_context() -> None:
    """Clear activity-scoped context (matches upstream finally block + idPostfix)."""
    XiansContext.set_workflow_id(None)
    XiansContext.set_workflow_type(None)
    XiansContext.set_agent_name(None)
    XiansContext.set_tenant_id(None)
    XiansContext.set_participant_id(None)
    XiansContext.set_authorization(None)
    XiansContext.set_request_id(None)
    XiansContext.set_id_postfix(None)
