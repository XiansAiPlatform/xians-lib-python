"""Unit tests for the scheduling package.

These tests target the Python scheduling feature for parity with the C#
``Xians.Lib.Agents.Scheduling`` implementation. They focus on the logic we
own (ID construction, builder validation, fluent API, collection routing)
and mock the Temporal client boundary so they can run without a live
Temporal server.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# The real temporalio package is an optional test dependency; make sure the
# scheduling modules can still be imported if it is missing from the test
# environment. We provide enough of the public API surface for the builder
# to compile-time resolve symbols (lazy imports are used at runtime for the
# actual construction, which we stub in per-test as needed).
try:  # pragma: no cover - exercised only when temporalio is installed
    import temporalio  # noqa: F401
    import temporalio.common  # noqa: F401
    _HAS_REAL_TEMPORALIO = True
except Exception:  # pragma: no cover - real temporalio absent in CI stub env
    _HAS_REAL_TEMPORALIO = False
    if "temporalio" not in sys.modules:
        temporalio_stub = types.ModuleType("temporalio")
        temporalio_stub.activity = SimpleNamespace(defn=lambda **_kwargs: (lambda f: f))
        temporalio_stub.workflow = SimpleNamespace()
        sys.modules["temporalio"] = temporalio_stub


from xians.agents.core.xians_context import XiansContext
from xians.agents.scheduling import (
    InvalidScheduleSpecError,
    ScheduleAlreadyExistsError,
    ScheduleBuilder,
    ScheduleCollection,
    ScheduleIdHelper,
    ScheduleNotFoundError,
    XiansSchedule,
)
from xians.agents.scheduling import schedule_extensions  # noqa: F401 - attach methods
from xians.agents.scheduling.models.activity_requests import (
    CreateCronScheduleRequest,
    CreateIntervalScheduleRequest,
)


# ---------------------------------------------------------------------------
# ScheduleIdHelper
# ---------------------------------------------------------------------------


class TestScheduleIdHelper:
    def test_full_schedule_id_with_postfix(self) -> None:
        got = ScheduleIdHelper.build_full_schedule_id(
            "tenant-1", "AgentX", "run-42", "daily-report"
        )
        assert got == "tenant-1:AgentX:run-42:daily-report"

    def test_full_schedule_id_without_postfix(self) -> None:
        got = ScheduleIdHelper.build_full_schedule_id(
            "tenant-1", "AgentX", None, "daily-report"
        )
        assert got == "tenant-1:AgentX:daily-report"

    def test_full_schedule_id_with_empty_postfix_preserves_segment(self) -> None:
        got = ScheduleIdHelper.build_full_schedule_id(
            "tenant-1", "AgentX", "", "daily-report"
        )
        assert got == "tenant-1:AgentX::daily-report"

    def test_full_workflow_id(self) -> None:
        got = ScheduleIdHelper.build_full_workflow_id(
            "tenant-1", "AgentX:Report", "run-42"
        )
        assert got == "tenant-1:AgentX:Report:run-42"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_already_exists_carries_schedule_id(self) -> None:
        ex = ScheduleAlreadyExistsError("my-schedule")
        assert ex.schedule_id == "my-schedule"
        assert "my-schedule" in str(ex)

    def test_not_found_carries_schedule_id(self) -> None:
        ex = ScheduleNotFoundError("missing")
        assert ex.schedule_id == "missing"
        assert "missing" in str(ex)

    def test_invalid_spec_is_xians_error(self) -> None:
        from xians.exceptions.v1.errors import XiansError

        assert issubclass(InvalidScheduleSpecError, XiansError)


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _make_builder(**overrides) -> ScheduleBuilder:
    """Build a ScheduleBuilder with a fake collection suitable for unit tests."""
    defaults = dict(
        schedule_name="s",
        agent_name="AgentX",
        system_scoped=False,
        tenant_id="tenant-1",
        workflow_type="AgentX:Report",
        collection=SimpleNamespace(get_temporal_client_async=AsyncMock(return_value=None)),
        id_postfix=None,
    )
    defaults.update(overrides)
    return ScheduleBuilder(**defaults)


class TestScheduleBuilderValidation:
    def test_construction_requires_schedule_name(self) -> None:
        with pytest.raises(ValueError):
            _make_builder(schedule_name="")

    def test_construction_requires_workflow_type(self) -> None:
        with pytest.raises(ValueError):
            _make_builder(workflow_type="")

    def test_with_cron_schedule_validates_empty(self) -> None:
        b = _make_builder()
        with pytest.raises(ValueError):
            b.with_cron_schedule("   ")

    def test_with_interval_schedule_validates_positive(self) -> None:
        b = _make_builder()
        with pytest.raises(ValueError):
            b.with_interval_schedule(timedelta(seconds=0))

    def test_with_timeout_validates_positive(self) -> None:
        b = _make_builder()
        with pytest.raises(ValueError):
            b.with_timeout(timedelta(seconds=0))

    def test_with_calendar_schedule_requires_time(self) -> None:
        b = _make_builder()
        with pytest.raises(ValueError):
            b.with_calendar_schedule(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_create_requires_spec_to_be_configured(self) -> None:
        b = _make_builder()
        with pytest.raises(InvalidScheduleSpecError):
            await b.create_async()

    def test_with_input_sets_args(self) -> None:
        b = _make_builder().with_input("summary", 42)
        assert b._workflow_args == ["summary", 42]

    def test_with_memo_is_copied(self) -> None:
        memo_in = {"owner": "ops"}
        b = _make_builder().with_memo(memo_in)
        memo_in["owner"] = "other"
        assert b._workflow_memo == {"owner": "ops"}


# ---------------------------------------------------------------------------
# Fluent extensions (daily, every_minutes, skip_if_running, …)
# ---------------------------------------------------------------------------


class TestFluentExtensions:
    def test_daily_builds_cron(self) -> None:
        b = _make_builder().daily(hour=9, minute=30)
        assert b._pending_spec is not None
        assert b._pending_spec.cron_expression == "30 9 * * *"

    def test_daily_validates_hour_range(self) -> None:
        with pytest.raises(ValueError):
            _make_builder().daily(hour=24)

    def test_hourly_builds_cron(self) -> None:
        b = _make_builder().hourly(minute=15)
        assert b._pending_spec.cron_expression == "15 * * * *"

    def test_weekly_builds_cron(self) -> None:
        b = _make_builder().weekly(day_of_week=1, hour=8, minute=0)
        assert b._pending_spec.cron_expression == "0 8 * * 1"

    def test_monthly_builds_cron(self) -> None:
        b = _make_builder().monthly(day_of_month=15, hour=8)
        assert b._pending_spec.cron_expression == "0 8 15 * *"

    def test_weekdays_builds_cron(self) -> None:
        b = _make_builder().weekdays(hour=9)
        assert b._pending_spec.cron_expression == "0 9 * * 1-5"

    def test_every_minutes_builds_interval(self) -> None:
        b = _make_builder().every_minutes(5)
        assert b._pending_spec.interval == timedelta(minutes=5)

    def test_every_hours_validates_positive(self) -> None:
        with pytest.raises(ValueError):
            _make_builder().every_hours(0)

    def test_every_days_with_multi_day_uses_interval(self) -> None:
        b = _make_builder().every_days(days=3)
        assert b._pending_spec.interval == timedelta(days=3)

    def test_every_days_with_single_day_uses_daily(self) -> None:
        b = _make_builder().every_days(days=1, hour=10, minute=30)
        assert b._pending_spec.cron_expression == "30 10 * * *"


# ---------------------------------------------------------------------------
# Overlap shortcuts
# ---------------------------------------------------------------------------


class TestOverlapExtensions:
    def _check_policy(self, method_name: str, expected_overlap: str) -> None:
        # Provide a tiny stub for temporalio.client so builder imports resolve.
        temporalio_client = sys.modules.setdefault(
            "temporalio.client", types.ModuleType("temporalio.client")
        )

        class _StubOverlap:
            SKIP = "SKIP"
            ALLOW_ALL = "ALLOW_ALL"
            BUFFER_ONE = "BUFFER_ONE"
            CANCEL_OTHER = "CANCEL_OTHER"
            TERMINATE_OTHER = "TERMINATE_OTHER"

        class _StubPolicy:
            def __init__(self, *, overlap: str = "", **_kw) -> None:
                self.overlap = overlap

        temporalio_client.ScheduleOverlapPolicy = _StubOverlap  # type: ignore[attr-defined]
        temporalio_client.SchedulePolicy = _StubPolicy  # type: ignore[attr-defined]

        b = _make_builder()
        getattr(b, method_name)()
        assert b._schedule_policy is not None
        assert b._schedule_policy.overlap == expected_overlap

    def test_skip_if_running(self) -> None:
        self._check_policy("skip_if_running", "SKIP")

    def test_allow_overlap(self) -> None:
        self._check_policy("allow_overlap", "ALLOW_ALL")

    def test_buffer_one(self) -> None:
        self._check_policy("buffer_one", "BUFFER_ONE")

    def test_cancel_other(self) -> None:
        self._check_policy("cancel_other", "CANCEL_OTHER")

    def test_terminate_other(self) -> None:
        self._check_policy("terminate_other", "TERMINATE_OTHER")


# ---------------------------------------------------------------------------
# ScheduleBuilder internals that don't need a live Temporal client
# ---------------------------------------------------------------------------


class TestScheduleBuilderInternals:
    def test_build_full_schedule_id_tenant_scoped(self) -> None:
        b = _make_builder(id_postfix="run-1")
        assert b._build_full_schedule_id() == "tenant-1:AgentX:run-1:s"

    def test_build_full_schedule_id_no_postfix(self) -> None:
        b = _make_builder(id_postfix=None)
        assert b._build_full_schedule_id() == "tenant-1:AgentX:s"

    def test_system_scoped_requires_workflow_context(self) -> None:
        b = _make_builder(system_scoped=True, tenant_id=None, id_postfix=None)
        XiansContext.clear()
        with pytest.raises(RuntimeError):
            b._effective_tenant_id()

    def test_build_memo_contains_system_metadata(self) -> None:
        XiansContext.clear()
        b = _make_builder(id_postfix="run-1").with_memo({"extra": "value"})
        memo = b._build_memo(tenant_id="tenant-1")
        assert memo["tenantId"] == "tenant-1"
        assert memo["agent"] == "AgentX"
        assert memo["idPostfix"] == "run-1"
        assert memo["systemScoped"] is False
        assert memo["extra"] == "value"
        assert memo["userId"] == ""

    @pytest.mark.skipif(
        not _HAS_REAL_TEMPORALIO, reason="Requires real temporalio package"
    )
    def test_standard_search_attributes_contain_four_keyword_keys(self) -> None:
        """The 4 standard search attributes (tenantId, agent, userId, idPostfix)
        are attached to every schedule automatically, mirroring the C# lib."""
        XiansContext.clear()
        b = _make_builder(id_postfix="run-1")
        sa = b._build_standard_search_attributes(tenant_id="tenant-1")
        pairs = {p.key.name: p.value for p in sa.search_attributes}
        assert pairs == {
            "tenantId": "tenant-1",
            "agent": "AgentX",
            "userId": "",
            "idPostfix": "run-1",
        }
        # All four keys are Keyword-typed (same as C# SearchAttributeKey.CreateKeyword)
        for pair in sa.search_attributes:
            assert pair.key.value_type is str

    @pytest.mark.skipif(
        not _HAS_REAL_TEMPORALIO, reason="Requires real temporalio package"
    )
    def test_resolve_search_attributes_merges_user_keys_with_standard(self) -> None:
        """User-provided attrs are preserved; standard keys fill the gaps."""
        from temporalio.common import (
            SearchAttributeKey,
            SearchAttributePair,
            TypedSearchAttributes,
        )

        XiansContext.clear()
        user_attrs = TypedSearchAttributes(
            search_attributes=[
                SearchAttributePair(
                    SearchAttributeKey.for_keyword("customKey"), "customValue"
                ),
                # User override of a standard key is kept as-is.
                SearchAttributePair(
                    SearchAttributeKey.for_keyword("tenantId"), "user-override"
                ),
            ]
        )
        b = _make_builder(id_postfix="run-1").with_typed_search_attributes(user_attrs)
        merged = b._resolve_effective_search_attributes(tenant_id="tenant-1")
        pairs = {p.key.name: p.value for p in merged.search_attributes}
        assert pairs["customKey"] == "customValue"
        assert pairs["tenantId"] == "user-override"  # user wins
        assert pairs["agent"] == "AgentX"  # filled from standard
        assert pairs["userId"] == ""
        assert pairs["idPostfix"] == "run-1"


# ---------------------------------------------------------------------------
# ScheduleCollection
# ---------------------------------------------------------------------------


def _make_collection(*, temporal_client) -> ScheduleCollection:
    async def _provider():
        return temporal_client

    return ScheduleCollection(
        agent_name="AgentX",
        system_scoped=False,
        tenant_id="tenant-1",
        get_temporal_client=_provider,
    )


class TestScheduleCollection:
    def test_create_requires_workflow_definition(self) -> None:
        collection = _make_collection(temporal_client=None)

        class NotAWorkflow:
            pass

        with pytest.raises(ValueError):
            collection.create("s", NotAWorkflow)

    def test_create_accepts_workflow_type_string(self) -> None:
        collection = _make_collection(temporal_client=None)
        builder = collection.create("s", "AgentX:Workflow")
        assert isinstance(builder, ScheduleBuilder)
        assert builder._workflow_type == "AgentX:Workflow"

    def test_create_accepts_workflow_class_with_defn(self) -> None:
        collection = _make_collection(temporal_client=None)

        class FakeDefn:
            name = "AgentX:Workflow"

        class FakeWorkflow:
            pass

        # Set via setattr to bypass Python's private-name mangling;
        # real Temporal sets this externally on the decorated class.
        setattr(FakeWorkflow, "__temporal_workflow_definition", FakeDefn())

        builder = collection.create("s", FakeWorkflow)
        assert builder._workflow_type == "AgentX:Workflow"

    @pytest.mark.asyncio
    async def test_get_async_raises_not_found_for_missing_schedule(self) -> None:
        handle = SimpleNamespace(
            id="tenant-1:AgentX:s",
            describe=AsyncMock(side_effect=Exception("schedule not found")),
        )
        temporal_client = SimpleNamespace(
            get_schedule_handle=MagicMock(return_value=handle),
        )
        collection = _make_collection(temporal_client=temporal_client)

        with pytest.raises(ScheduleNotFoundError):
            await collection.get_async("s", id_postfix=None)

    @pytest.mark.asyncio
    async def test_exists_async_returns_false_when_missing(self) -> None:
        handle = SimpleNamespace(
            id="tenant-1:AgentX:s",
            describe=AsyncMock(side_effect=Exception("not found")),
        )
        temporal_client = SimpleNamespace(
            get_schedule_handle=MagicMock(return_value=handle),
        )
        collection = _make_collection(temporal_client=temporal_client)

        assert await collection.exists_async("s") is False

    @pytest.mark.asyncio
    async def test_exists_async_returns_true_when_present(self) -> None:
        handle = SimpleNamespace(
            id="tenant-1:AgentX:s",
            describe=AsyncMock(return_value=object()),
        )
        temporal_client = SimpleNamespace(
            get_schedule_handle=MagicMock(return_value=handle),
        )
        collection = _make_collection(temporal_client=temporal_client)

        assert await collection.exists_async("s") is True

    @pytest.mark.asyncio
    async def test_pause_unpause_trigger_delete_delegate_to_handle(self) -> None:
        handle = SimpleNamespace(
            id="tenant-1:AgentX:s",
            describe=AsyncMock(return_value=object()),
            pause=AsyncMock(),
            unpause=AsyncMock(),
            trigger=AsyncMock(),
            delete=AsyncMock(),
        )
        temporal_client = SimpleNamespace(
            get_schedule_handle=MagicMock(return_value=handle),
        )
        collection = _make_collection(temporal_client=temporal_client)

        await collection.pause_async("s", note="maint")
        handle.pause.assert_awaited_once_with(note="maint")

        await collection.unpause_async("s")
        handle.unpause.assert_awaited_once()

        await collection.trigger_async("s")
        handle.trigger.assert_awaited_once()

        await collection.delete_async("s")
        handle.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_async_raises_when_client_missing(self) -> None:
        collection = _make_collection(temporal_client=None)
        with pytest.raises(RuntimeError):
            await collection.get_async("s")


# ---------------------------------------------------------------------------
# XiansSchedule wrapper
# ---------------------------------------------------------------------------


class TestXiansSchedule:
    def test_requires_handle(self) -> None:
        with pytest.raises(ValueError):
            XiansSchedule(None)  # type: ignore[arg-type]

    def test_id_and_get_handle(self) -> None:
        handle = SimpleNamespace(id="abc")
        schedule = XiansSchedule(handle)
        assert schedule.id == "abc"
        assert schedule.get_handle() is handle

    @pytest.mark.asyncio
    async def test_pause_delegates(self) -> None:
        handle = SimpleNamespace(id="abc", pause=AsyncMock())
        await XiansSchedule(handle).pause_async(note="x")
        handle.pause.assert_awaited_once_with(note="x")

    @pytest.mark.asyncio
    async def test_describe_wraps_errors(self) -> None:
        handle = SimpleNamespace(
            id="abc", describe=AsyncMock(side_effect=RuntimeError("boom"))
        )
        with pytest.raises(RuntimeError):
            await XiansSchedule(handle).describe_async()


# ---------------------------------------------------------------------------
# Activity request dataclasses (serialization parity with C# ActivityRequests)
# ---------------------------------------------------------------------------


class TestActivityRequests:
    def test_cron_request_defaults(self) -> None:
        req = CreateCronScheduleRequest(
            schedule_name="s",
            cron_expression="0 9 * * *",
            workflow_type="AgentX:Wf",
        )
        assert req.workflow_input == []
        assert req.timezone is None
        assert req.id_postfix is None

    def test_interval_request_defaults(self) -> None:
        req = CreateIntervalScheduleRequest(
            schedule_name="s",
            workflow_type="AgentX:Wf",
            interval_seconds=60.0,
        )
        assert req.workflow_input == []
        assert req.id_postfix is None
        assert req.interval_seconds == 60.0
