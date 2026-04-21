"""Unit tests for ``WorkflowMetadataResolver``.

These tests verify behavioural parity with the C#
``Xians.Lib.Agents.Core.WorkflowMetadataResolver`` class: value extraction from
typed search attributes / memo, workflow-ID parsing, collection building, and
the serializable-dict round-trip used when passing metadata through activities.
"""

from __future__ import annotations

import pytest

try:  # pragma: no cover - exercised only when temporalio is installed
    import temporalio  # noqa: F401
    import temporalio.common  # noqa: F401

    _HAS_REAL_TEMPORALIO = True
except Exception:  # pragma: no cover
    _HAS_REAL_TEMPORALIO = False

from xians.agents.core.workflow_metadata_resolver import (
    WorkflowMetadataKeys,
    WorkflowMetadataResolver,
)


pytestmark = pytest.mark.skipif(
    not _HAS_REAL_TEMPORALIO,
    reason="temporalio package required for WorkflowMetadataResolver tests",
)


# ---------------------------------------------------------------------------
# Key constants — parity with C# `WorkflowConstants.Keys`
# ---------------------------------------------------------------------------


class TestWorkflowMetadataKeys:
    def test_standard_keys_values(self) -> None:
        assert WorkflowMetadataKeys.TENANT_ID == "tenantId"
        assert WorkflowMetadataKeys.AGENT == "agent"
        assert WorkflowMetadataKeys.USER_ID == "userId"
        assert WorkflowMetadataKeys.ID_POSTFIX == "idPostfix"
        assert WorkflowMetadataKeys.SYSTEM_SCOPED == "systemScoped"

    def test_standard_metadata_keys_tuple_matches_csharp_order(self) -> None:
        assert WorkflowMetadataResolver.STANDARD_METADATA_KEYS == (
            "tenantId",
            "agent",
            "userId",
            "idPostfix",
        )


# ---------------------------------------------------------------------------
# ID postfix parsing — parity with C# ParseIdPostfixFromWorkflowId
# ---------------------------------------------------------------------------


class TestParseIdPostfixFromWorkflowId:
    def test_parses_fourth_segment(self) -> None:
        got = WorkflowMetadataResolver.parse_id_postfix_from_workflow_id(
            "tenant-1:AgentX:Main:postfix-42"
        )
        assert got == "postfix-42"

    def test_strips_scheduled_timestamp_suffix(self) -> None:
        # Note: a full ISO timestamp contains ``:`` separators which ``split(":")``
        # would break across segments, so Temporal's appended suffix that lands
        # on segment 4 is the compact hour-only form (e.g. ``-2026-02-17T22``).
        got = WorkflowMetadataResolver.parse_id_postfix_from_workflow_id(
            "tenant-1:AgentX:Main:postfix-42-2026-02-17T22"
        )
        assert got == "postfix-42"

    def test_strips_multiple_timestamp_suffixes(self) -> None:
        got = WorkflowMetadataResolver.parse_id_postfix_from_workflow_id(
            "t:A:W:run-1-2026-02-17T22-2026-02-18T00-2026-02-18T02"
        )
        assert got == "run-1"

    def test_timestamp_only_postfix_preserves_original(self) -> None:
        # If stripping the timestamp would produce an empty string the C#
        # implementation returns the original segment.
        got = WorkflowMetadataResolver.parse_id_postfix_from_workflow_id(
            "t:A:W:-2026-02-17T22"
        )
        assert got == "-2026-02-17T22"

    def test_returns_none_for_less_than_four_segments(self) -> None:
        assert (
            WorkflowMetadataResolver.parse_id_postfix_from_workflow_id(
                "tenant:agent:workflow"
            )
            is None
        )

    def test_returns_none_for_empty_string(self) -> None:
        assert (
            WorkflowMetadataResolver.parse_id_postfix_from_workflow_id("") is None
        )


# ---------------------------------------------------------------------------
# Value extraction — parity with C# GetValueFromSearchAttributes / GetValueFromMemo
# ---------------------------------------------------------------------------


class TestValueExtraction:
    def test_get_value_from_none_search_attrs_returns_none(self) -> None:
        assert (
            WorkflowMetadataResolver.get_value_from_search_attributes(
                None, "userId"
            )
            is None
        )

    def test_get_value_from_search_attrs_reads_keyword_value(self) -> None:
        attrs = WorkflowMetadataResolver.build_search_attributes(
            "tenant-1", "AgentX", "user-42", "postfix-9"
        )
        assert (
            WorkflowMetadataResolver.get_value_from_search_attributes(
                attrs, "userId"
            )
            == "user-42"
        )
        assert (
            WorkflowMetadataResolver.get_value_from_search_attributes(
                attrs, "idPostfix"
            )
            == "postfix-9"
        )
        assert (
            WorkflowMetadataResolver.get_value_from_search_attributes(
                attrs, "missing"
            )
            is None
        )

    def test_get_value_from_memo_reads_value(self) -> None:
        memo = {"userId": "user-7", "tenantId": "t-1"}
        assert (
            WorkflowMetadataResolver.get_value_from_memo(memo, "userId")
            == "user-7"
        )

    def test_get_value_from_memo_strips_surrounding_quotes(self) -> None:
        memo = {"userId": '"user-42"'}
        assert (
            WorkflowMetadataResolver.get_value_from_memo(memo, "userId")
            == "user-42"
        )

    def test_get_value_from_memo_returns_none_for_missing_key(self) -> None:
        assert (
            WorkflowMetadataResolver.get_value_from_memo({"a": "b"}, "userId")
            is None
        )

    def test_get_value_from_memo_returns_none_for_none_memo(self) -> None:
        assert (
            WorkflowMetadataResolver.get_value_from_memo(None, "userId") is None
        )


# ---------------------------------------------------------------------------
# Build / reconstruct — parity with C# BuildSearchAttributes and
# ExtractToSerializableDictionary / ReconstructFromDictionary
# ---------------------------------------------------------------------------


class TestBuildAndSerialize:
    def test_build_search_attributes_contains_four_keyword_keys(self) -> None:
        attrs = WorkflowMetadataResolver.build_search_attributes(
            "tenant-1", "AgentX", "user-42", "postfix-9"
        )
        names = {pair.key.name for pair in attrs.search_attributes}
        assert names == {"tenantId", "agent", "userId", "idPostfix"}

    def test_extract_to_dict_defaults_to_standard_keys(self) -> None:
        attrs = WorkflowMetadataResolver.build_search_attributes(
            "tenant-1", "AgentX", "user-42", "postfix-9"
        )
        got = WorkflowMetadataResolver.extract_to_serializable_dictionary(attrs)
        assert got == {
            "tenantId": "tenant-1",
            "agent": "AgentX",
            "userId": "user-42",
            "idPostfix": "postfix-9",
        }

    def test_extract_to_dict_honours_explicit_keys(self) -> None:
        attrs = WorkflowMetadataResolver.build_search_attributes(
            "t", "A", "u", "p"
        )
        got = WorkflowMetadataResolver.extract_to_serializable_dictionary(
            attrs, "userId"
        )
        assert got == {"userId": "u"}

    def test_extract_to_dict_returns_none_when_empty(self) -> None:
        # An attribute collection with no standard keys should yield None.
        empty = WorkflowMetadataResolver.reconstruct_from_dictionary(
            {"custom": "value"}
        )
        got = WorkflowMetadataResolver.extract_to_serializable_dictionary(empty)
        # ``extract`` only looks at standard keys — none present => None.
        assert got is None

    def test_reconstruct_roundtrips_through_dict(self) -> None:
        original = WorkflowMetadataResolver.build_search_attributes(
            "tenant-1", "AgentX", "user-42", "postfix-9"
        )
        as_dict = WorkflowMetadataResolver.extract_to_serializable_dictionary(
            original
        )
        rebuilt = WorkflowMetadataResolver.reconstruct_from_dictionary(as_dict)
        assert rebuilt is not None
        assert (
            WorkflowMetadataResolver.get_value_from_search_attributes(
                rebuilt, "userId"
            )
            == "user-42"
        )
        assert (
            WorkflowMetadataResolver.get_value_from_search_attributes(
                rebuilt, "idPostfix"
            )
            == "postfix-9"
        )

    def test_reconstruct_returns_none_for_empty_dict(self) -> None:
        assert (
            WorkflowMetadataResolver.reconstruct_from_dictionary(None) is None
        )
        assert WorkflowMetadataResolver.reconstruct_from_dictionary({}) is None


# ---------------------------------------------------------------------------
# Context gating — outside workflow / activity everything returns None/raises
# ---------------------------------------------------------------------------


class TestContextGating:
    def test_get_workflow_id_raises_outside_context(self) -> None:
        with pytest.raises(RuntimeError):
            WorkflowMetadataResolver.get_workflow_id()

    def test_get_from_workflow_context_returns_none_outside_workflow(self) -> None:
        assert (
            WorkflowMetadataResolver.get_from_workflow_context("userId") is None
        )

    def test_resolve_id_postfix_sync_returns_none_outside_context(self) -> None:
        assert WorkflowMetadataResolver.resolve_id_postfix_sync() is None

    @pytest.mark.asyncio
    async def test_resolve_id_postfix_async_returns_none_outside_context(
        self,
    ) -> None:
        assert (
            await WorkflowMetadataResolver.resolve_id_postfix_async() is None
        )

    @pytest.mark.asyncio
    async def test_resolve_search_attributes_for_child_returns_none_outside_context(
        self,
    ) -> None:
        assert (
            await WorkflowMetadataResolver.resolve_search_attributes_for_child_async(
                "tenant-1", "AgentX", None
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_fetch_workflow_description_returns_none_outside_activity(
        self,
    ) -> None:
        class _NoopClient:
            def get_workflow_handle(self, *_args, **_kwargs):
                raise AssertionError("should not be called outside activity")

        got = await WorkflowMetadataResolver.fetch_workflow_description_async(
            _NoopClient()  # type: ignore[arg-type]
        )
        assert got is None
