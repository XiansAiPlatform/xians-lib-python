"""Custom workflow that demonstrates business metrics logging.

Runs an activity that reports various business metrics to test the
Xians metrics feature: approvals, documents, emails, performance, etc.
"""

from __future__ import annotations

import time
from datetime import timedelta

from temporalio import activity, workflow

from custom_input_workflow import AGENT_NAME


@activity.defn(name="ReportBusinessMetrics")
async def report_business_metrics(scenario: str) -> str:
    """Activity that reports different business metrics based on scenario.

    Demonstrates the metrics API for:
    - Approvals (submitted, approved, rejected)
    - Documents (generated, viewed)
    - Emails (sent, received)
    - Performance (processing time, records processed)
    """
    from xians.agents.core import XiansContext

    # Simulate some "work" to measure
    time.sleep(0.1)

    metrics = XiansContext.Metrics

    if scenario == "approvals":
        await metrics \
            .with_metrics(
                ("approvals", "submitted", 1, "count"),
                ("approvals", "pending", 2, "count"),
            ) \
            .report_async()
        return "Reported approval metrics: 1 submitted, 2 pending"

    if scenario == "documents":
        await metrics \
            .with_metrics(
                ("documents", "generated", 3, "count"),
                ("documents", "viewed", 5, "count"),
            ) \
            .report_async()
        return "Reported document metrics: 3 generated, 5 viewed"

    if scenario == "emails":
        await metrics \
            .with_metrics(
                ("emails", "sent", 4, "count"),
                ("emails", "received", 7, "count"),
            ) \
            .report_async()
        return "Reported email metrics: 4 sent, 7 received"

    if scenario == "performance":
        elapsed_ms = 150  # Simulated processing time
        records = 42
        await metrics \
            .with_metrics(
                ("performance", "processing_time", elapsed_ms, "ms"),
                ("performance", "records_processed", records, "count"),
            ) \
            .report_async()
        return f"Reported performance metrics: {elapsed_ms}ms, {records} records"

    if scenario == "mixed":
        await metrics \
            .with_custom_identifier("business-metrics-demo") \
            .with_metadata("version", "1.0") \
            .with_metrics(
                ("approvals", "submitted", 1, "count"),
                ("documents", "generated", 2, "count"),
                ("emails", "sent", 3, "count"),
                ("performance", "processing_time", 125, "ms"),
            ) \
            .report_async()
        return "Reported mixed business metrics with custom identifier and metadata"

    # Default: report workflow started
    await metrics \
        .with_metric("workflow", "started", 1, "count") \
        .report_async()
    return f"Reported workflow started (unknown scenario: {scenario})"


@workflow.defn(name=f"{AGENT_NAME}:Business Metrics Workflow")
class BusinessMetricsWorkflow:
    """Custom workflow that logs different business metrics.

    Start from the UI with parameter:
      scenario: "approvals" | "documents" | "emails" | "performance" | "mixed"

    Each scenario reports different metric categories to test the metrics API.
    """

    @workflow.run
    async def run(self, scenario: str = "mixed") -> str:
        return await workflow.execute_activity(
            report_business_metrics,
            scenario,
            start_to_close_timeout=timedelta(seconds=30),
        )
