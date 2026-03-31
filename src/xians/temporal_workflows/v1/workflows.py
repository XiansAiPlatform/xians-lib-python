"""Built-in Temporal workflows for Xians SDK v1.

Replaces InvokeAgentWorkflow + ConversationWorkflow with a unified BuiltinWorkflow
matching C# BuiltinWorkflow behavior: signal-driven message queue with handler dispatch.
"""

import asyncio
import dataclasses
import logging
from collections import deque
from typing import Any, Optional

from temporalio import workflow

from .models import InboundMessage, InboundMessagePayload, WorkflowHandlerMetadata, WorkflowOptions

logger = logging.getLogger(__name__)


def _normalize_dict(raw: dict) -> dict[str, Any]:
    """Build a lowercase-key lookup from a dict so field matching is case-insensitive."""
    return {k.lower(): v for k, v in raw.items()} if isinstance(raw, dict) else {}


def _parse_inbound_message(raw: Any) -> InboundMessage:
    """Convert raw signal data (dict or InboundMessage) into an InboundMessage.

    The Temporal Python SDK may fail to populate nested dataclass fields if
    the JSON key casing from the C# server doesn't exactly match the Python
    field names.  This helper does case-insensitive matching so that both
    ``Payload`` / ``payload`` and ``ParticipantId`` / ``participantId`` work.
    """
    if isinstance(raw, InboundMessage):
        return raw

    if not isinstance(raw, dict):
        workflow.logger.warning(
            f"[DEBUG] Signal data is neither InboundMessage nor dict, type={type(raw).__name__}"
        )
        return InboundMessage()

    norm = _normalize_dict(raw)

    payload_raw = norm.get("payload")
    if isinstance(payload_raw, dict):
        pn = _normalize_dict(payload_raw)
        payload = InboundMessagePayload(
            agent=pn.get("agent") or "",
            threadId=pn.get("threadid") or "",
            participantId=pn.get("participantid") or "",
            authorization=pn.get("authorization"),
            text=pn.get("text") or "",
            requestId=pn.get("requestid") or "",
            hint=pn.get("hint") or "",
            scope=pn.get("scope") or "",
            data=pn.get("data"),
            type=pn.get("type") or "chat",
            history=pn.get("history"),
        )
    elif isinstance(payload_raw, InboundMessagePayload):
        payload = payload_raw
    else:
        payload = InboundMessagePayload()

    return InboundMessage(
        payload=payload,
        sourceAgent=norm.get("sourceagent") or "",
        sourceWorkflowId=norm.get("sourceworkflowid") or "",
        sourceWorkflowType=norm.get("sourceworkflowtype") or "",
    )

# Static handler registry (matches C# BuiltinWorkflow._handlersByWorkflowType)
_handlers_by_workflow_type: dict[str, WorkflowHandlerMetadata] = {}
_workflow_options: dict[str, WorkflowOptions] = {}


@workflow.defn(name="BuiltinWorkflow")
class BuiltinWorkflow:
    """Core workflow matching C# BuiltinWorkflow.

    Handles all conversation types (chat, data, file, webhook) through
    a signal-driven message queue with handler dispatch.
    """

    def __init__(self) -> None:
        self._message_queue: deque[InboundMessage] = deque()
        self._handlers_finished: bool = False
        self._event_count: int = 0

    @workflow.run
    async def run(self, *args: Any) -> None:
        """Entry point. Starts the message processing loop.

        Accepts *args because the Xians server may pass workflow parameters
        via StartWorkflowAsync (matching C# where RunAsync() ignores them).
        """
        await self._process_messages_loop()

    @workflow.signal(name="HandleInboundChatOrData")
    async def handle_inbound_chat_or_data(self, raw_message: Any) -> None:
        """Signal handler for inbound messages.
        Matches C# BuiltinWorkflow.HandleInboundChatOrData.

        Accepts ``Any`` instead of ``InboundMessage`` so the Temporal SDK
        returns the raw deserialized dict.  This avoids silent field-name
        mismatches (e.g. PascalCase vs camelCase) that cause empty payloads.
        """
        workflow.logger.info(
            f"[DEBUG] Raw signal data received type={type(raw_message).__name__} value={raw_message!r}"
        )

        message = _parse_inbound_message(raw_message)

        payload = message.payload
        workflow.logger.info(
            f"[DEBUG] Parsed InboundMessage participantId={payload.participantId!r} "
            f"text={payload.text[:80]!r} type={payload.type!r} "
            f"requestId={payload.requestId!r} threadId={payload.threadId!r} "
            f"scope={payload.scope!r}"
        )

        self._message_queue.append(message)
        self._event_count += 1

    async def _process_messages_loop(self) -> None:
        """Top-level loop with error handling."""
        try:
            await self._process_messages_loop_core()
        except Exception as e:
            if "ContinueAsNew" in type(e).__name__:
                raise
            if isinstance(e, asyncio.CancelledError):
                workflow.logger.info("Workflow cancelled")
                return
            workflow.logger.error(f"Unhandled error in message loop: {e}")

    async def _process_messages_loop_core(self) -> None:
        """Main processing loop matching C# ProcessMessagesLoopCoreAsync.

        1. Wait for messages in queue (with optional inactivity timeout)
        2. Dequeue and process via MessageProcessor
        3. Check for continue-as-new
        """
        wf_info = workflow.info()
        workflow_type = wf_info.workflow_type
        workflow_id = wf_info.workflow_id
        options = _workflow_options.get(workflow_type, WorkflowOptions())
        inactivity_timeout = options.inactivity_timeout

        while True:
            try:
                if inactivity_timeout:
                    await workflow.wait_condition(
                        lambda: len(self._message_queue) > 0 or self._should_continue_as_new(options),
                        timeout=inactivity_timeout,
                    )
                else:
                    await workflow.wait_condition(
                        lambda: len(self._message_queue) > 0 or self._should_continue_as_new(options),
                    )
            except asyncio.TimeoutError:
                self._handlers_finished = True
                self._continue_as_new_if_needed(options)
                return

            if self._should_continue_as_new(options):
                self._continue_as_new_if_needed(options)

            while self._message_queue:
                message = self._message_queue.popleft()
                try:
                    from .message_processor import MessageProcessor
                    wf_run_id = wf_info.run_id
                    await MessageProcessor.process_message(
                        message=message,
                        workflow_id=workflow_id,
                        workflow_type=workflow_type,
                        workflow_run_id=wf_run_id,
                    )
                except Exception as e:
                    workflow.logger.error(f"Error processing message: {e}")
                    try:
                        from .message_response_helper import MessageResponseHelper
                        await MessageResponseHelper.send_error_response(
                            message=message,
                            error_message=str(e),
                            workflow_id=workflow_id,
                            workflow_type=workflow_type,
                        )
                    except Exception as err:
                        workflow.logger.error(f"Failed to send error response: {err}")

    def _should_continue_as_new(self, options: WorkflowOptions) -> bool:
        """Check if workflow should continue-as-new."""
        if not self._handlers_finished:
            return False
        max_history = options.max_history_length or 1000
        if self._event_count >= max_history:
            return True
        try:
            return workflow.info().continue_as_new_suggested
        except AttributeError:
            return False

    def _continue_as_new_if_needed(self, options: WorkflowOptions) -> None:
        """Trigger continue-as-new if conditions are met."""
        if self._should_continue_as_new(options):
            workflow.continue_as_new()

    # --- Static Handler Registration (matches C# static methods) ---

    @staticmethod
    def register_chat_handler(
        workflow_type: str,
        handler: object,
        agent_name: str,
        tenant_id: Optional[str] = None,
        system_scoped: bool = False,
    ) -> None:
        metadata = _handlers_by_workflow_type.setdefault(
            workflow_type,
            WorkflowHandlerMetadata(agent_name=agent_name, tenant_id=tenant_id, system_scoped=system_scoped),
        )
        metadata.chat_handler = handler

    @staticmethod
    def register_data_handler(
        workflow_type: str,
        handler: object,
        agent_name: str,
        tenant_id: Optional[str] = None,
        system_scoped: bool = False,
    ) -> None:
        metadata = _handlers_by_workflow_type.setdefault(
            workflow_type,
            WorkflowHandlerMetadata(agent_name=agent_name, tenant_id=tenant_id, system_scoped=system_scoped),
        )
        metadata.data_handler = handler

    @staticmethod
    def register_file_upload_handler(
        workflow_type: str,
        handler: object,
        agent_name: str,
        tenant_id: Optional[str] = None,
        system_scoped: bool = False,
    ) -> None:
        metadata = _handlers_by_workflow_type.setdefault(
            workflow_type,
            WorkflowHandlerMetadata(agent_name=agent_name, tenant_id=tenant_id, system_scoped=system_scoped),
        )
        metadata.file_upload_handler = handler

    @staticmethod
    def register_webhook_handler(
        workflow_type: str,
        handler: object,
        agent_name: str,
        tenant_id: Optional[str] = None,
        system_scoped: bool = False,
    ) -> None:
        metadata = _handlers_by_workflow_type.setdefault(
            workflow_type,
            WorkflowHandlerMetadata(agent_name=agent_name, tenant_id=tenant_id, system_scoped=system_scoped),
        )
        metadata.webhook_handler = handler

    @staticmethod
    def register_workflow_options(workflow_type: str, options: WorkflowOptions) -> None:
        _workflow_options[workflow_type] = options

    @staticmethod
    def clear_handlers_for_tests() -> None:
        _handlers_by_workflow_type.clear()
        _workflow_options.clear()


_named_workflow_classes: dict[str, type] = {}


def create_named_builtin_workflow(workflow_type_name: str) -> type:
    """Create a BuiltinWorkflow registered under a specific Temporal workflow type name.

    Mirrors the C# ``DynamicWorkflowTypeBuilder`` which uses
    ``System.Reflection.Emit`` to create a runtime subclass of
    ``BuiltinWorkflow`` annotated with ``[Workflow("Agent:Workflow")]``.

    The Temporal Python SDK's ``_Definition`` is a **frozen** dataclass, so we
    use ``dataclasses.replace()`` to produce a new definition with the
    correct ``name`` and ``cls``.  The class itself is created with ``type()``
    (not a local ``class`` statement) to avoid the SDK's
    ``<locals>`` qualname check on ``@workflow.run``.
    """
    if workflow_type_name in _named_workflow_classes:
        return _named_workflow_classes[workflow_type_name]

    base_defn = getattr(BuiltinWorkflow, "__temporal_workflow_definition", None)
    if base_defn is None:
        raise RuntimeError("BuiltinWorkflow is missing __temporal_workflow_definition")

    new_cls = type(workflow_type_name, (BuiltinWorkflow,), {
        "__module__": BuiltinWorkflow.__module__,
        "__qualname__": workflow_type_name,
    })

    new_defn = dataclasses.replace(
        base_defn,
        name=workflow_type_name,
        cls=new_cls,
        sandboxed=False,
    )
    setattr(new_cls, "__temporal_workflow_definition", new_defn)

    _named_workflow_classes[workflow_type_name] = new_cls
    return new_cls


__all__ = ["BuiltinWorkflow", "create_named_builtin_workflow"]
