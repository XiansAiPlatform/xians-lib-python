import base64
from pathlib import Path

import pytest
from pydantic import ValidationError

from temporalio.client import TLSConfig

from xians.models.v1.configs import TemporalConfig, TemporalTLSConfig
from xians.temporal_workflows.v1.tls_utils import resolve_cert_bytes
from xians.temporal_workflows.v1.worker_runner import WorkerHost


def test_no_tls_config_returns_none():
    host = WorkerHost(TemporalConfig(address="localhost:7233", namespace="default"))
    assert host._build_temporal_tls_config(None) is None


def test_root_ca_pem_sets_tlsconfig_server_root():
    tls = TemporalTLSConfig(root_ca_pem="PEM_CONTENT", pem_is_base64=False, enabled=True)
    host = WorkerHost(TemporalConfig(address="localhost:7233", namespace="default", tls=tls))
    cfg = host._build_temporal_tls_config(tls)
    assert isinstance(cfg, TLSConfig)
    assert cfg.server_root_ca_cert == b"PEM_CONTENT"


def test_root_ca_path_loaded(tmp_path: Path):
    pem_path = tmp_path / "ca.pem"
    pem_path.write_bytes(b"CA_BYTES")
    tls = TemporalTLSConfig(root_ca_path=str(pem_path), enabled=True)
    host = WorkerHost(TemporalConfig(address="localhost:7233", namespace="default", tls=tls))
    cfg = host._build_temporal_tls_config(tls)
    assert isinstance(cfg, TLSConfig)
    assert cfg.server_root_ca_cert == b"CA_BYTES"


def test_client_cert_and_key_pem_set_both():
    tls = TemporalTLSConfig(client_cert_pem="CERT", client_key_pem="KEY", enabled=True)
    host = WorkerHost(TemporalConfig(address="localhost:7233", namespace="default", tls=tls))
    cfg = host._build_temporal_tls_config(tls)
    assert isinstance(cfg, TLSConfig)
    assert cfg.client_cert == b"CERT"
    assert cfg.client_private_key == b"KEY"


def test_client_cert_without_key_raises():
    with pytest.raises(ValidationError):
        TemporalTLSConfig(client_cert_pem="CERT", enabled=True)


def test_key_without_client_cert_raises():
    with pytest.raises(ValidationError):
        TemporalTLSConfig(client_key_pem="KEY", enabled=True)


def test_pem_is_base64_decodes():
    ca_bytes = b"CA_PEM_BYTES"
    ca_b64 = base64.b64encode(ca_bytes).decode("utf-8")
    tls = TemporalTLSConfig(root_ca_pem=ca_b64, pem_is_base64=True, enabled=True)
    host = WorkerHost(TemporalConfig(address="localhost:7233", namespace="default", tls=tls))
    cfg = host._build_temporal_tls_config(tls)
    assert isinstance(cfg, TLSConfig)
    assert cfg.server_root_ca_cert == ca_bytes

