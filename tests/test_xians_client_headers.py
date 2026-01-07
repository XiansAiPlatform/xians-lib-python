"""Tests for XiansServerClient header injection and auth modes."""

import base64
import json

import httpx
import pytest
from pydantic import SecretStr

from xians.interfaces.v1.xians_client import XiansServerClient
from xians.models.v1.configs import XiansServerConfig


@pytest.mark.asyncio
async def test_bearer_and_tenant_headers_injected() -> None:
    """Ensure Authorization Bearer and X-Tenant-Id headers are applied for /api/agent/* requests."""

    cert_value = base64.b64encode(b"cert-data-123").decode()
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        captured["tenant"] = request.headers.get("X-Tenant-Id")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        bearer_cert_base64=SecretStr(cert_value),
        tenant_id="tenant-123",
    )
    client = XiansServerClient(config, transport=transport)

    await client.fetch_temporal_settings()

    assert captured["auth"] == f"Bearer {cert_value}"
    assert captured["tenant"] == "tenant-123"

    await client.close()


@pytest.mark.asyncio
async def test_x_api_key_header_injected() -> None:
    """Ensure X-API-Key header is applied when auth_mode is x_api_key and tenant header not added for non-agent routes."""

    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["api_key"] = request.headers.get("X-API-Key")
        captured["tenant"] = request.headers.get("X-Tenant-Id")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    config = XiansServerConfig(
        server_url="https://api.example.com",
        auth_mode="x_api_key",
        x_api_key=SecretStr("super-secret-api-key"),
    )
    client = XiansServerClient(config, transport=transport)

    await client.get_document("doc-1")

    assert captured["api_key"] == "super-secret-api-key"
    assert captured["tenant"] is None

    await client.close()

