"""Tests for Document DB models, service, client payloads, and collection behavior."""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# Provide a tiny temporalio stub for environments where temporalio native
# package components are unavailable during test collection.
if "temporalio" not in sys.modules:
    temporalio_stub = types.ModuleType("temporalio")
    temporalio_stub.activity = SimpleNamespace(defn=lambda **_kwargs: (lambda f: f))
    temporalio_stub.workflow = SimpleNamespace()
    sys.modules["temporalio"] = temporalio_stub

from xians.agents.documents.document_collection import DocumentCollection
from xians.agents.documents.document_service import DocumentService
from xians.agents.documents.models import Document, DocumentQuery


class TestDocumentModels:
    """Model serialization behavior."""

    def test_document_to_api_dict_serializes_datetime(self) -> None:
        doc = Document(
            id="doc-1",
            content={"k": "v"},
            updated_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        )

        payload = doc.to_api_dict()

        assert payload["id"] == "doc-1"
        assert payload["updatedAt"] == "2026-01-01T00:00:00+00:00"

    def test_document_query_to_api_dict_serializes_datetime(self) -> None:
        query = DocumentQuery(
            type="profile",
            created_after=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        )

        payload = query.to_api_dict()

        assert payload["type"] == "profile"
        assert payload["createdAfter"] == "2026-01-01T00:00:00+00:00"


class TestDocumentService:
    """Service behavior and request shaping."""

    @pytest.mark.asyncio
    async def test_update_async_includes_required_content_field(self) -> None:
        mock_client = SimpleNamespace(update_document=AsyncMock(return_value=True))
        service = DocumentService(http_client=mock_client)
        doc = Document(id="doc-1", content=None)

        ok = await service.update_async(doc, tenant_id="tenant-1")

        assert ok is True
        mock_client.update_document.assert_awaited_once()
        sent_doc = mock_client.update_document.await_args.args[0]
        assert "content" in sent_doc
        assert sent_doc["content"] is None
        assert isinstance(sent_doc.get("updatedAt"), str)


class TestDocumentCollection:
    """Collection-level scoping logic."""

    @pytest.mark.asyncio
    async def test_query_async_auto_scopes_agent_id(self) -> None:
        collection = DocumentCollection(
            agent_name="Agent-A",
            http_client=SimpleNamespace(),
            tenant_id="tenant-1",
            system_scoped=False,
        )
        fake_executor = SimpleNamespace(
            query_async=AsyncMock(return_value=[]),
        )
        collection._executor = fake_executor

        query = DocumentQuery(type="profile")
        await collection.query_async(query)

        assert query.agent_id == "Agent-A"
        fake_executor.query_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_key_uses_query_not_get_by_key_endpoint(self) -> None:
        collection = DocumentCollection(
            agent_name="Agent-A",
            http_client=SimpleNamespace(),
            tenant_id="tenant-1",
            system_scoped=False,
        )
        expected_doc = Document(id="doc-1", type="profile", key="user-1", content={})
        fake_executor = SimpleNamespace(
            query_async=AsyncMock(return_value=[expected_doc]),
        )
        collection._executor = fake_executor

        got = await collection.get_by_key_async("profile", "user-1")

        assert got is not None
        assert got.id == "doc-1"
        fake_executor.query_async.assert_awaited_once()
        sent_query = fake_executor.query_async.await_args.args[0]
        assert sent_query.type == "profile"
        assert sent_query.key == "user-1"
        assert sent_query.limit == 1
        assert sent_query.agent_id == "Agent-A"
