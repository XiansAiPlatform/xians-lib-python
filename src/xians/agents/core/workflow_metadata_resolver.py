"""Workflow metadata resolver — Python port of the C# ``WorkflowMetadataResolver``.

Mirrors ``Xians.Lib/Xians.Lib/Agents/Core/WorkflowMetadataResolver.cs`` one-to-one.

Central resolver for workflow metadata (``tenantId``, ``agent``, ``userId``,
``idPostfix``, etc.). Extracts values from typed search attributes, memo,
workflow ID, or the full workflow description. Works in both workflow and
activity contexts; in activity context it can fetch the parent workflow
description via the Temporal client for accurate metadata (avoids workflow ID
timestamp pollution).

Design notes
------------

- Method names use snake_case to match the rest of the Python library, but the
  behavior is a 1:1 mirror of the C# class. A short mapping is documented in
  each docstring.
- All public methods are ``@staticmethod`` — the class is a namespace, exactly
  like the C# ``internal static class``.
- Temporal imports are lazy at call-site so this module remains importable in
  test environments where ``temporalio`` is not installed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - import-only hints
    from temporalio.client import Client, WorkflowExecutionDescription
    from temporalio.common import TypedSearchAttributes


# ---------------------------------------------------------------------------
# Standard metadata keys (mirror of Xians.Lib.Common.WorkflowConstants.Keys)
# ---------------------------------------------------------------------------


class WorkflowMetadataKeys:
    """Standard memo / search attribute keys.

    Mirrors C# ``Xians.Lib.Common.WorkflowConstants.Keys``.  Kept on a class
    so it reads naturally from call sites (``WorkflowMetadataKeys.USER_ID``)
    and so new keys can be added without changing the module surface.
    """

    TENANT_ID = "tenantId"
    AGENT = "agent"
    USER_ID = "userId"
    ID_POSTFIX = "idPostfix"
    SYSTEM_SCOPED = "systemScoped"

    # Task workflow specific keys
    TASK_TITLE = "taskTitle"
    TASK_DESCRIPTION = "taskDescription"
    TASK_ACTIONS = "taskActions"


# Temporal appends a timestamp suffix to scheduled workflow IDs.  The regex
# matches one or more ``-YYYY-MM-DDTHH[:MM:SS[.fff]Z]`` suffixes.  Mirrors the
# C# ``TemporalScheduledTimestampSuffixRegex``.
_TEMPORAL_SCHEDULED_TIMESTAMP_SUFFIX_RE = re.compile(
    r"(?:-\d{4}-\d{2}-\d{2}T[\d:.Z]+)+$"
)


class WorkflowMetadataResolver:
    """Static resolver for workflow metadata.

    Mirrors C# ``Xians.Lib.Agents.Core.WorkflowMetadataResolver``.
    """

    # ------------------------------------------------------------------
    # Standard keys (mirror of the C# `StandardMetadataKeys` array)
    # ------------------------------------------------------------------

    STANDARD_METADATA_KEYS: tuple[str, ...] = (
        WorkflowMetadataKeys.TENANT_ID,
        WorkflowMetadataKeys.AGENT,
        WorkflowMetadataKeys.USER_ID,
        WorkflowMetadataKeys.ID_POSTFIX,
    )

    # ------------------------------------------------------------------
    # Value extraction (mirror of #region "Value extraction")
    # ------------------------------------------------------------------

    @staticmethod
    def get_value_from_search_attributes(
        search_attrs: Any, key_name: str
    ) -> Optional[str]:
        """Extract a string value from a ``TypedSearchAttributes`` by key name.

        Mirrors C# ``GetValueFromSearchAttributes``. Returns ``None`` when
        ``search_attrs`` is ``None``, the key is missing, or the value cannot
        be coerced to a string.
        """
        if search_attrs is None:
            return None
        try:
            from temporalio.common import SearchAttributeKey

            key = SearchAttributeKey.for_keyword(key_name)
            try:
                value = search_attrs.get(key)
            except Exception:
                value = None

            if value is None:
                # Fallback: iterate the ``search_attributes`` list when ``get``
                # uses identity-equality on the typed key object.
                pairs = getattr(search_attrs, "search_attributes", []) or []
                for pair in pairs:
                    if getattr(pair.key, "name", None) == key_name:
                        value = pair.value
                        break

            if value is None:
                return None
            text = str(value)
            return text or None
        except Exception:
            return None

    @staticmethod
    def get_value_from_memo(memo: Any, key_name: str) -> Optional[str]:
        """Extract a string value from a workflow memo dictionary.

        Mirrors C# ``GetValueFromMemo``. Strips surrounding double quotes to
        match the behavior of C# reading an ``IEncodedRawValue`` payload.
        """
        if memo is None:
            return None
        try:
            value = memo.get(key_name) if hasattr(memo, "get") else None
            if value is None:
                return None
            text = str(value).strip('"')
            return text or None
        except Exception:
            return None

    @staticmethod
    def parse_id_postfix_from_workflow_id(workflow_id: str) -> Optional[str]:
        """Parse the idPostfix segment out of a Xians workflow ID.

        Workflow ID format: ``{tenantId}:{agentName}:{workflowName}:{idPostfix}``.
        For scheduled workflows Temporal appends a timestamp suffix (e.g.
        ``-2026-02-17T13:31:53Z``); this function strips it.

        Mirrors C# ``ParseIdPostfixFromWorkflowId``.
        """
        if not workflow_id:
            return None
        try:
            parts = workflow_id.split(":")
            if len(parts) < 4:
                return None
            id_part = parts[3]
            if not id_part:
                return None
            without_timestamp = _TEMPORAL_SCHEDULED_TIMESTAMP_SUFFIX_RE.sub(
                "", id_part
            )
            return without_timestamp or id_part
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Workflow context resolution (mirror of #region "Workflow context resolution")
    # ------------------------------------------------------------------

    @staticmethod
    def _in_workflow() -> bool:
        """Best-effort check for ``Workflow.InWorkflow``."""
        try:
            from temporalio import workflow as _workflow

            _workflow.info()
            return True
        except Exception:
            return False

    @staticmethod
    def _in_activity() -> bool:
        """Best-effort check for ``ActivityExecutionContext.HasCurrent``."""
        try:
            from temporalio import activity as _activity

            _activity.info()
            return True
        except Exception:
            return False

    @staticmethod
    def get_workflow_id() -> str:
        """Resolve the current workflow ID from workflow or activity context.

        Mirrors C# ``GetWorkflowId``. Raises :class:`RuntimeError` when not in
        workflow or activity context (equivalent to C#
        ``InvalidOperationException``).
        """
        try:
            from temporalio import workflow as _workflow

            info = _workflow.info()
            workflow_id = getattr(info, "workflow_id", None)
            if workflow_id:
                return workflow_id
            raise RuntimeError(
                "Workflow ID is not available from Temporal workflow info."
            )
        except RuntimeError:
            raise
        except Exception:
            pass

        try:
            from temporalio import activity as _activity

            info = _activity.info()
            workflow_id = getattr(info, "workflow_id", None)
            if workflow_id:
                return workflow_id
            raise RuntimeError(
                "Workflow ID is not available from Temporal activity info."
            )
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("Not in workflow or activity context.")

    @staticmethod
    def get_workflow_run_id() -> str:
        """Resolve the current workflow run ID from workflow or activity context.

        Mirrors C# ``GetWorkflowRunId``.
        """
        try:
            from temporalio import workflow as _workflow

            info = _workflow.info()
            run_id = getattr(info, "run_id", None)
            if run_id:
                return run_id
            raise RuntimeError(
                "Run ID is not available from Temporal workflow info."
            )
        except RuntimeError:
            raise
        except Exception:
            pass

        try:
            from temporalio import activity as _activity

            info = _activity.info()
            run_id = getattr(info, "workflow_run_id", None)
            if run_id:
                return run_id
            raise RuntimeError(
                "Workflow run ID is not available from Temporal activity info."
            )
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("Not in workflow or activity context.")

    @staticmethod
    def get_from_workflow_context(key_name: str) -> Optional[str]:
        """Resolve a metadata value from workflow search attrs → memo.

        Only works when currently executing inside a Temporal workflow.
        Mirrors C# ``GetFromWorkflowContext``.
        """
        from_attrs = WorkflowMetadataResolver._get_from_search_attributes(
            key_name
        )
        if from_attrs:
            return from_attrs
        return WorkflowMetadataResolver._get_from_workflow_memo(key_name)

    @staticmethod
    def _get_from_search_attributes(key_name: str) -> Optional[str]:
        """Mirror of C# private ``GetFromSearchAttributes``."""
        try:
            from temporalio import workflow as _workflow

            if not WorkflowMetadataResolver._in_workflow():
                return None
            info = _workflow.info()
            attrs = getattr(info, "typed_search_attributes", None)
            return WorkflowMetadataResolver.get_value_from_search_attributes(
                attrs, key_name
            )
        except Exception:
            return None

    @staticmethod
    def _get_from_workflow_memo(key_name: str) -> Optional[str]:
        """Mirror of C# private ``GetFromWorkflowMemo``."""
        try:
            from temporalio import workflow as _workflow

            if not WorkflowMetadataResolver._in_workflow():
                return None
            if not hasattr(_workflow, "memo"):
                return None
            memo = _workflow.memo()
            return WorkflowMetadataResolver.get_value_from_memo(memo, key_name)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Workflow description (activity + client)  (mirror of same C# region)
    # ------------------------------------------------------------------

    @staticmethod
    async def fetch_workflow_description_async(
        client: "Client",
    ) -> Optional["WorkflowExecutionDescription"]:
        """Fetch the parent workflow description when running inside an activity.

        Mirrors C# ``FetchWorkflowDescriptionAsync``. Returns ``None`` outside
        activity context or when the describe call fails (e.g. the parent has
        already closed and history was scrubbed).
        """
        if not WorkflowMetadataResolver._in_activity():
            return None
        try:
            from temporalio import activity as _activity

            info = _activity.info()
            workflow_id = getattr(info, "workflow_id", None)
            run_id = getattr(info, "workflow_run_id", None)
            if not workflow_id:
                return None
            handle = client.get_workflow_handle(workflow_id, run_id=run_id)
            return await handle.describe()
        except Exception:
            return None

    @staticmethod
    async def get_from_description(
        description: Optional["WorkflowExecutionDescription"], key_name: str
    ) -> Optional[str]:
        """Extract a value from a fetched workflow description.

        Mirrors C# ``GetFromDescription``: typed search attributes first, then
        memo. The Python SDK exposes ``memo()`` as an ``async`` method on the
        description object, so this helper is ``async`` where the C# one is
        sync.
        """
        if description is None:
            return None

        attrs = getattr(description, "typed_search_attributes", None)
        from_attrs = WorkflowMetadataResolver.get_value_from_search_attributes(
            attrs, key_name
        )
        if from_attrs:
            return from_attrs

        try:
            if hasattr(description, "memo"):
                memo = await description.memo()
                from_memo = WorkflowMetadataResolver.get_value_from_memo(
                    memo, key_name
                )
                if from_memo:
                    return from_memo
        except Exception:
            return None
        return None

    @staticmethod
    async def resolve_search_attributes_for_child_async(
        tenant_id: str,
        agent_name: str,
        client: Optional["Client"],
    ) -> Optional["TypedSearchAttributes"]:
        """Resolve typed search attributes for a child / scheduled workflow.

        Priority mirrors C# ``ResolveSearchAttributesForChildAsync``:

        1. Inside a workflow — return ``workflow.info().typed_search_attributes``.
        2. Inside an activity with a client — fetch the parent workflow
           description and reuse its typed search attributes.
        3. Fallback: build a fresh collection from mined ``userId`` /
           ``idPostfix`` values plus the supplied tenant / agent.
        4. Outside workflow/activity: ``None``.
        """
        if WorkflowMetadataResolver._in_workflow():
            try:
                from temporalio import workflow as _workflow

                info = _workflow.info()
                return getattr(info, "typed_search_attributes", None)
            except Exception:
                return None

        if not WorkflowMetadataResolver._in_activity() or client is None:
            return None

        description = await WorkflowMetadataResolver.fetch_workflow_description_async(
            client
        )
        if description is not None:
            parent_attrs = getattr(description, "typed_search_attributes", None)
            if parent_attrs is not None:
                return parent_attrs

        user_id = (
            await WorkflowMetadataResolver.get_from_description(
                description, WorkflowMetadataKeys.USER_ID
            )
            or ""
        )
        id_postfix = (
            await WorkflowMetadataResolver.get_from_description(
                description, WorkflowMetadataKeys.ID_POSTFIX
            )
            or ""
        )
        return WorkflowMetadataResolver.build_search_attributes(
            tenant_id, agent_name, user_id, id_postfix
        )

    @staticmethod
    async def resolve_id_postfix_async(
        client: Optional["Client"] = None,
    ) -> Optional[str]:
        """Resolve idPostfix, preferring parent description when available.

        Mirrors C# ``ResolveIdPostfixAsync``.
        """
        if (
            not WorkflowMetadataResolver._in_workflow()
            and not WorkflowMetadataResolver._in_activity()
        ):
            return None

        if client is not None and WorkflowMetadataResolver._in_activity():
            try:
                description = await WorkflowMetadataResolver.fetch_workflow_description_async(
                    client
                )
                from_description = await WorkflowMetadataResolver.get_from_description(
                    description, WorkflowMetadataKeys.ID_POSTFIX
                )
                if from_description:
                    return from_description
            except Exception:
                pass  # fall through to sync resolution

        return WorkflowMetadataResolver.resolve_id_postfix_sync()

    @staticmethod
    def resolve_id_postfix_sync() -> Optional[str]:
        """Resolve idPostfix synchronously from workflow context.

        Mirrors C# ``ResolveIdPostfixSync``: search attrs → memo → workflow ID
        parsing.  Only parses the workflow ID when inside workflow / activity
        context (same gating as C#).
        """
        from_context = WorkflowMetadataResolver.get_from_workflow_context(
            WorkflowMetadataKeys.ID_POSTFIX
        )
        if from_context:
            return from_context

        if (
            WorkflowMetadataResolver._in_workflow()
            or WorkflowMetadataResolver._in_activity()
        ):
            try:
                return WorkflowMetadataResolver.parse_id_postfix_from_workflow_id(
                    WorkflowMetadataResolver.get_workflow_id()
                )
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Search attribute collection building (mirror of same C# region)
    # ------------------------------------------------------------------

    @staticmethod
    def build_search_attributes(
        tenant_id: str,
        agent_name: str,
        user_id: str,
        id_postfix: str,
    ) -> "TypedSearchAttributes":
        """Build a ``TypedSearchAttributes`` holding the 4 standard keyword keys.

        Mirrors C# ``BuildSearchAttributes``.
        """
        from temporalio.common import (
            SearchAttributeKey,
            SearchAttributePair,
            TypedSearchAttributes,
        )

        values: dict[str, str] = {
            WorkflowMetadataKeys.TENANT_ID: tenant_id,
            WorkflowMetadataKeys.AGENT: agent_name,
            WorkflowMetadataKeys.USER_ID: user_id,
            WorkflowMetadataKeys.ID_POSTFIX: id_postfix,
        }
        pairs = [
            SearchAttributePair(SearchAttributeKey.for_keyword(key), value)
            for key, value in values.items()
        ]
        return TypedSearchAttributes(search_attributes=pairs)

    @staticmethod
    def extract_to_serializable_dictionary(
        search_attributes: Any,
        *keys: str,
    ) -> Optional[dict[str, Any]]:
        """Extract named values from typed search attrs into a dict.

        Mirrors C# ``ExtractToSerializableDictionary``.  Defaults to the 4
        standard keys when no explicit keys are supplied.  Returns ``None``
        when the result would be empty (matching C#).
        """
        if search_attributes is None:
            return None

        effective_keys = keys if keys else WorkflowMetadataResolver.STANDARD_METADATA_KEYS
        result: dict[str, Any] = {}
        for key_name in effective_keys:
            value = WorkflowMetadataResolver.get_value_from_search_attributes(
                search_attributes, key_name
            )
            if value is not None:
                result[key_name] = value
        return result or None

    @staticmethod
    def reconstruct_from_dictionary(
        search_attrs: Optional[dict[str, Any]],
    ) -> Optional["TypedSearchAttributes"]:
        """Reconstruct a ``TypedSearchAttributes`` from a plain dict.

        Mirrors C# ``ReconstructFromDictionary``.  All values are treated as
        ``Keyword`` search attributes, same as C#.
        """
        if not search_attrs:
            return None

        from temporalio.common import (
            SearchAttributeKey,
            SearchAttributePair,
            TypedSearchAttributes,
        )

        pairs = [
            SearchAttributePair(
                SearchAttributeKey.for_keyword(str(key)),
                "" if value is None else str(value),
            )
            for key, value in search_attrs.items()
        ]
        if not pairs:
            return None
        return TypedSearchAttributes(search_attributes=pairs)


__all__ = [
    "WorkflowMetadataKeys",
    "WorkflowMetadataResolver",
]
