"""Custom Temporal workflow that accepts start parameters.

This is intentionally simple: it proves custom workflows can be registered and
started (parameter-driven), independent from the BuiltinWorkflow chat/data
signal-driven pipeline.
"""

from __future__ import annotations

from temporalio import workflow


AGENT_NAME = "Custom Workflow Test Agent5"


@workflow.defn(name=f"{AGENT_NAME}:Custom Input Workflow")
class CustomInputWorkflow:
    @workflow.run
    async def run(
        self,
        input: str,
        times: int = 1,
        uppercase: bool = False,
    ) -> str:
        text = (input or "") * max(1, int(times))
        return text.upper() if uppercase else text

