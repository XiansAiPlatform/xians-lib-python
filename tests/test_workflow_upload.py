"""Tests for XiansServerClient workflow definition upload with correct payload format."""

import tempfile
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from xians.constants.v1.core import WorkflowType
from xians.exceptions.v1.errors import XiansServerError
from xians.interfaces.v1.xians_client import XiansServerClient
from xians.models.v1.configs import XiansServerConfig
from xians.models.v1.entities import AgentDefinition, WorkflowDefinition


@pytest.mark.asyncio
async def test_upload_workflow_definition_correct_endpoint() -> None:
    """Ensure workflow definition is POSTed to /api/agent/definitions (not /api/agent/definitions/workflows)."""

    captured_request: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["path"] = request.url.path
        captured_request["headers"] = dict(request.headers)
        captured_request["json"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    # Use temp cache directory to avoid hash caching
    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="TestAgent",
            system_scoped=False,
            agent_key="TestAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="Conversational",
            workers=1,
            agent_key="TestAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        # Verify endpoint
        assert captured_request["method"] == "POST"
        assert captured_request["path"] == "/api/agent/definitions"

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_camelcase_payload() -> None:
    """Ensure workflow definition payload uses camelCase keys."""

    import json

    captured_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.read().decode("utf-8")))
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="MyAgent",
            system_scoped=False,
            agent_key="MyAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="Conversational",
            workers=1,
            agent_key="MyAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        # Verify camelCase keys are present
        assert "workflowType" in captured_payload
        assert "systemScoped" in captured_payload

        # Verify snake_case keys are NOT present
        assert "workflow_type" not in captured_payload
        assert "system_scoped" not in captured_payload

        # Verify required fields
        assert captured_payload["agent"] == "MyAgent"
        assert captured_payload["workflowType"] == "MyAgent:BuiltIn Workflow-Conversational"
        assert captured_payload["name"] == "Conversational"
        assert captured_payload["systemScoped"] is False
        assert captured_payload["workers"] == 1

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_workers_is_int() -> None:
    """Ensure workers field is sent as integer, not string."""

    import json

    captured_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.read().decode("utf-8")))
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="WorkerAgent",
            system_scoped=False,
            agent_key="WorkerAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="MultiWorker",
            workers=3,
            agent_key="WorkerAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        assert isinstance(captured_payload["workers"], int)
        assert captured_payload["workers"] == 3

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_content_type_header() -> None:
    """Ensure Content-Type: application/json header is set."""

    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="HeaderAgent",
            system_scoped=False,
            agent_key="HeaderAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="HeaderWorkflow",
            workers=1,
            agent_key="HeaderAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        assert "content-type" in captured_headers
        assert captured_headers["content-type"] == "application/json"

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_400_error_handling() -> None:
    """Ensure 400 Bad Request errors include detailed information."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": "Invalid payload", "details": "workflowType is required"},
        )

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="ErrorAgent",
            system_scoped=False,
            agent_key="ErrorAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="ErrorWorkflow",
            workers=1,
            agent_key="ErrorAgent",
        )

        with pytest.raises(XiansServerError) as exc_info:
            await client.upload_workflow_definition(agent, workflow)

        error = exc_info.value
        assert error.status_code == 400
        assert "400" in str(error)  # Check for status code in error message
        assert "/api/agent/definitions" in str(error)
        assert error.response_body is not None
        assert "Invalid payload" in error.response_body

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_system_scoped_true() -> None:
    """Ensure systemScoped is correctly set to true for system-scoped agents."""

    import json

    captured_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.read().decode("utf-8")))
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="SystemAgent",
            system_scoped=True,
            agent_key="SystemAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="SystemWorkflow",
            workers=1,
            agent_key="SystemAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        assert captured_payload["systemScoped"] is True

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_no_null_required_fields() -> None:
    """Ensure required fields are never null in the payload."""

    import json

    captured_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.read().decode("utf-8")))
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="RequiredAgent",
            system_scoped=False,
            agent_key="RequiredAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="RequiredWorkflow",
            workers=1,
            agent_key="RequiredAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        # All required fields must be present and not None
        required_fields = ["agent", "workflowType", "name", "systemScoped", "workers"]
        for field in required_fields:
            assert field in captured_payload
            assert captured_payload[field] is not None

        await client.close()


@pytest.mark.asyncio
async def test_upload_workflow_definition_with_tenant_header() -> None:
    """Ensure X-Tenant-Id header is included when tenant_id is configured."""

    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"workflow_id": "test-workflow"})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr("valid-cert-abc123def456"),
        tenant_id="tenant-456",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        client = XiansServerClient(config, cache_dir=Path(tmpdir), transport=transport)

        agent = AgentDefinition(
            name="TenantAgent",
            system_scoped=False,
            agent_key="TenantAgent",
        )

        workflow = WorkflowDefinition(
            workflow_type=WorkflowType.CONVERSATIONAL,
            name="TenantWorkflow",
            workers=1,
            agent_key="TenantAgent",
        )

        await client.upload_workflow_definition(agent, workflow)

        assert "x-tenant-id" in captured_headers
        assert captured_headers["x-tenant-id"] == "tenant-456"

        await client.close()

