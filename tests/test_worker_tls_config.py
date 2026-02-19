"""Tests for TLSConfig construction in WorkerHost.connect."""

import base64
import pytest

from xians.exceptions.v1.errors import TemporalError
from xians.temporal_workflows.v1.worker_runner import WorkerHost
from xians.models.v1.configs import TemporalConfig


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.mark.asyncio
async def test_tls_config_with_root_and_client_cert_key(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _b64(b"root-ca")
    cert = _b64(b"client-cert")
    key = _b64(b"client-key")

    cfg = TemporalConfig(
        host="localhost",
        port=7233,
        namespace="default",
        tls_enabled=True,
        server_root_ca_cert_base64=root,
        client_cert_base64=cert,
        client_private_key_base64=key,
    )

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    async def fake_connect(*args, **kwargs):
        return DummyClient(*args, **kwargs)

    monkeypatch.setattr("xians.temporal_workflows.v1.worker_runner.Client.connect", staticmethod(fake_connect))

    host = WorkerHost(cfg)
    await host.connect()

    assert host.client.kwargs["tls"].server_root_ca_cert == b"root-ca"
    assert host.client.kwargs["tls"].client_cert == b"client-cert"
    assert host.client.kwargs["tls"].client_private_key == b"client-key"


@pytest.mark.asyncio
async def test_tls_config_requires_cert_and_key_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    cert = _b64(b"client-cert")

    cfg = TemporalConfig(
        host="localhost",
        port=7233,
        namespace="default",
        tls_enabled=True,
        client_cert_base64=cert,
    )

    host = WorkerHost(cfg)
    with pytest.raises(TemporalError):
        await host.connect()

