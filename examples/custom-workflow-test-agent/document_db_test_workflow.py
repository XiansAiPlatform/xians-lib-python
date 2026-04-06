"""Custom workflow that tests Document DB operations from a Temporal activity.

Exercises the full Document DB API: save, get, get_by_key, query, update,
delete, delete_many, exists — all via XiansContext.Documents within an
activity, proving context-aware execution works end-to-end.

Start this workflow from the UI with an optional scenario parameter.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow

from custom_input_workflow import AGENT_NAME


@activity.defn(name="TestDocumentDB")
async def test_document_db(scenario: str = "full") -> str:
    """Activity that exercises all Document DB operations.

    Runs inside a Temporal activity so XiansContext resolves the current
    agent and its DocumentCollection automatically.
    """
    from xians.agents.core import XiansContext
    from xians.agents.documents import Document, DocumentOptions, DocumentQuery

    docs = XiansContext.Documents
    results: dict[str, Any] = {"scenario": scenario, "steps": []}

    def log_step(name: str, data: Any) -> None:
        results["steps"].append({"step": name, "data": data})

    try:
        # ── 1. Save with Type+Key (default upsert) ──
        doc1 = Document(
            type="test-profile",
            key="user-001",
            content={"name": "Alice", "plan": "premium", "credits": 100},
            metadata={"env": "test", "priority": "high"},
        )
        saved1 = await docs.save_async(doc1)
        log_step("save_with_key", {
            "id": saved1.id,
            "type": saved1.type,
            "key": saved1.key,
            "agent_id": saved1.agent_id,
        })

        # ── 2. Save a second document ──
        doc2 = Document(
            type="test-profile",
            key="user-002",
            content={"name": "Bob", "plan": "basic", "credits": 50},
            metadata={"env": "test", "priority": "low"},
        )
        saved2 = await docs.save_async(doc2)
        log_step("save_second", {"id": saved2.id, "key": saved2.key})

        # ── 3. Save with TTL ──
        session_doc = Document(
            type="test-session",
            key="session-abc",
            content={"token": "xyz-123", "active": True},
        )
        saved_session = await docs.save_async(
            session_doc,
            options=DocumentOptions(ttl_minutes=5),
        )
        log_step("save_with_ttl", {
            "id": saved_session.id,
            "expires_at": str(saved_session.expires_at),
        })

        # ── 4. Get by ID ──
        fetched = await docs.get_async(saved1.id)
        log_step("get_by_id", {
            "found": fetched is not None,
            "name": fetched.content.get("name") if fetched and isinstance(fetched.content, dict) else None,
        })

        # ── 5. Get by Type+Key ──
        by_key = await docs.get_by_key_async("test-profile", "user-001")
        log_step("get_by_key", {
            "found": by_key is not None,
            "id": by_key.id if by_key else None,
        })

        # ── 6. Query by type ──
        query_results = await docs.query_async(DocumentQuery(
            type="test-profile",
            limit=10,
        ))
        log_step("query_by_type", {
            "count": len(query_results),
            "keys": [d.key for d in query_results],
        })

        # ── 7. Query with metadata filters ──
        filtered = await docs.query_async(DocumentQuery(
            type="test-profile",
            metadata_filters={"priority": "high"},
            limit=10,
        ))
        log_step("query_with_metadata", {
            "count": len(filtered),
            "keys": [d.key for d in filtered],
        })

        # ── 8. Update ──
        if fetched:
            fetched.content = {"name": "Alice", "plan": "premium", "credits": 200}
            updated = await docs.update_async(fetched)
            log_step("update", {"success": updated, "id": fetched.id})

            verify = await docs.get_async(fetched.id)
            credits = (
                verify.content.get("credits")
                if verify and isinstance(verify.content, dict)
                else None
            )
            log_step("verify_update", {"credits": credits})

        # ── 9. Exists ──
        exists = await docs.exists_async(saved1.id)
        log_step("exists", {"id": saved1.id, "exists": exists})

        # ── 10. Save another for upsert test ──
        upsert_doc = Document(
            type="test-profile",
            key="user-001",
            content={"name": "Alice Updated", "plan": "enterprise", "credits": 999},
        )
        upserted = await docs.save_async(upsert_doc)
        log_step("upsert", {
            "id": upserted.id,
            "same_id_as_original": upserted.id == saved1.id,
            "name": upserted.content.get("name") if isinstance(upserted.content, dict) else None,
        })

        # ── 11. Delete one ──
        deleted = await docs.delete_async(saved2.id)
        log_step("delete_one", {"id": saved2.id, "deleted": deleted})

        verify_deleted = await docs.get_async(saved2.id)
        log_step("verify_delete", {"found_after_delete": verify_deleted is not None})

        # ── 12. Delete many ──
        remaining_ids = [saved1.id, saved_session.id]
        delete_count = await docs.delete_many_async(remaining_ids)
        log_step("delete_many", {
            "requested": len(remaining_ids),
            "deleted": delete_count,
        })

        results["success"] = True

    except Exception as ex:
        results["success"] = False
        results["error"] = str(ex)
        activity.logger.error("Document DB test failed: %s", ex, exc_info=True)

    return json.dumps(results, indent=2, default=str)


@workflow.defn(name=f"{AGENT_NAME}:Document DB Test Workflow")
class DocumentDBTestWorkflow:
    """Custom workflow that runs TestDocumentDB activity and returns the report.

    Start from the UI with an optional scenario parameter. It exercises
    the full Document DB API and returns a JSON report.
    """

    @workflow.run
    async def run(self, scenario: str = "full") -> str:
        return await workflow.execute_activity(
            test_document_db,
            scenario,
            start_to_close_timeout=timedelta(seconds=60),
        )
