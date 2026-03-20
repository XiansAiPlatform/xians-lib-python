"""Tests for the metrics module."""

import pytest

from xians.agents.metrics import (
    ContextAwareUsageReportBuilder,
    MetricValue,
    MetricsCollection,
    UsageReportRequest,
)


class TestMetricValue:
    """Test MetricValue model."""

    def test_creates_with_required_fields(self) -> None:
        m = MetricValue(category="tokens", type="total", value=150.0)
        assert m.category == "tokens"
        assert m.type == "total"
        assert m.value == 150.0
        assert m.unit == "count"

    def test_creates_with_custom_unit(self) -> None:
        m = MetricValue(category="perf", type="latency", value=42.5, unit="ms")
        assert m.unit == "ms"


class TestUsageReportRequest:
    """Test UsageReportRequest model."""

    def test_model_dump_for_api_excludes_none(self) -> None:
        r = UsageReportRequest(
            metrics=[MetricValue(category="t", type="t", value=1.0)],
            tenant_id="tenant-1",
        )
        d = r.model_dump_for_api()
        assert "tenantId" in d
        assert d["tenantId"] == "tenant-1"
        assert "metrics" in d
        assert len(d["metrics"]) == 1
        assert d["metrics"][0]["category"] == "t"
        assert "participantId" not in d  # None excluded


class TestMetricsCollection:
    """Test MetricsCollection."""

    def test_track_returns_builder(self) -> None:
        coll = MetricsCollection(
            agent_name="TestAgent",
            http_client=object(),
        )
        builder = coll.track()
        assert isinstance(builder, ContextAwareUsageReportBuilder)

    def test_for_model_returns_builder(self) -> None:
        coll = MetricsCollection(
            agent_name="TestAgent",
            http_client=object(),
        )
        builder = coll.for_model("gpt-4")
        assert isinstance(builder, ContextAwareUsageReportBuilder)
        assert builder._model == "gpt-4"

    def test_with_metric_returns_builder(self) -> None:
        coll = MetricsCollection(
            agent_name="TestAgent",
            http_client=object(),
        )
        builder = coll.with_metric("tokens", "total", 100, "tokens")
        assert isinstance(builder, ContextAwareUsageReportBuilder)
        assert len(builder._metrics) == 1
        assert builder._metrics[0].category == "tokens"
        assert builder._metrics[0].value == 100


class TestContextAwareUsageReportBuilder:
    """Test ContextAwareUsageReportBuilder."""

    @pytest.fixture
    def mock_collection(self) -> MetricsCollection:
        return MetricsCollection(
            agent_name="TestAgent",
            http_client=object(),
        )

    def test_with_metric_chains(self, mock_collection: MetricsCollection) -> None:
        builder = mock_collection.track().with_metric("a", "b", 1.0)
        assert builder is not None
        assert len(builder._metrics) == 1

    def test_with_metrics_chains(self, mock_collection: MetricsCollection) -> None:
        builder = mock_collection.track().with_metrics(
            ("t", "p", 45, "tokens"),
            ("t", "c", 105, "tokens"),
        )
        assert len(builder._metrics) == 2

    def test_for_model_sets_model(self, mock_collection: MetricsCollection) -> None:
        builder = mock_collection.track().for_model("gpt-4")
        assert builder._model == "gpt-4"

    def test_with_custom_identifier(self, mock_collection: MetricsCollection) -> None:
        builder = mock_collection.track().with_custom_identifier("msg-123")
        assert builder._custom_identifier == "msg-123"
