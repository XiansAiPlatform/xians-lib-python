"""Activities for Logging Test Workflow.

Kept separate from the workflow module so Temporal's workflow sandbox does not
import ``httpx`` (via ``xians.logging``) at workflow validation time.
"""

from __future__ import annotations

import json
import logging

from temporalio import activity

from xians.logging import LoggingServices, XiansLogger

stdlib_logger = logging.getLogger(__name__)
xians_logger = XiansLogger.for_type("examples.custom_workflow_test_agent.logging_test")


@activity.defn(name="RunLoggingTest")
async def run_logging_test(scenario: str) -> str:
    """Emit logs from an activity and return queue stats."""
    scenario = (scenario or "all").lower()
    results: list[str] = []

    if scenario in ("basic", "all"):
        xians_logger.debug("Logging test: debug log from activity")
        xians_logger.trace("Logging test: trace log from activity")
        xians_logger.info("Logging test: info log from activity")
        xians_logger.warning("Logging test: warning log from activity")
        xians_logger.error("Logging test: error log from activity")
        xians_logger.critical("Logging test: critical log from activity")
        stdlib_logger.info("Logging test: stdlib logger info from activity")
        results.append("basic_logging: OK")

    if scenario in ("error", "all"):
        try:
            raise ValueError("Intentional logging test exception")
        except Exception:
            xians_logger.exception("Logging test: exception log from activity")
            results.append("error_logging: OK")

    svc = LoggingServices.get_instance()
    queued, retrying = svc.get_stats()

    report = {
        "scenario": scenario,
        "results": results,
        "queued_logs": queued,
        "retrying_logs": retrying,
        "note": "Logs are batched; allow ~30s for server visibility by default.",
    }
    return json.dumps(report, indent=2)
