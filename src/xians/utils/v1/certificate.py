"""Certificate parsing utilities for Xians SDK v1.

Parses Base64-encoded X.509 certificates (PFX/PKCS12) to extract
tenant ID, user ID, and other metadata. Matches C# CertificateReader behavior.
"""

import base64
import hashlib
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12

from ...exceptions.v1.errors import ConfigurationError


def parse_certificate(api_key: str) -> dict:
    """Parse a Base64-encoded PFX/PKCS12 certificate and extract metadata.

    The certificate subject format is: CN={userId}, OU={userId}, O={tenantId}

    Args:
        api_key: Base64-encoded PFX certificate

    Returns:
        dict with tenant_id, user_id, subject, thumbprint, expires_at

    Raises:
        ConfigurationError: If certificate cannot be parsed or is expired
    """
    try:
        normalized = api_key.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
        cert_bytes = base64.b64decode(normalized)
    except Exception as e:
        raise ConfigurationError(f"Failed to decode ApiKey as Base64: {e}")

    certificate = None
    try:
        _private_key, certificate, _additional_certs = pkcs12.load_key_and_certificates(
            cert_bytes, password=None
        )
    except Exception:
        try:
            certificate = x509.load_der_x509_certificate(cert_bytes)
        except Exception as e:
            raise ConfigurationError(f"Failed to parse certificate from ApiKey: {e}")

    if certificate is None:
        raise ConfigurationError("No certificate found in ApiKey")

    subject = certificate.subject
    tenant_id = _get_subject_field(subject, NameOID.ORGANIZATION_NAME)
    user_id = _get_subject_field(subject, NameOID.ORGANIZATIONAL_UNIT_NAME)

    if not tenant_id:
        raise ConfigurationError("Certificate missing Organization (O=) field for TenantId")
    if not user_id:
        raise ConfigurationError("Certificate missing Organizational Unit (OU=) field for UserId")

    der_bytes = certificate.public_bytes(Encoding.DER)
    thumbprint = hashlib.sha1(der_bytes).hexdigest().upper()

    expires_at = certificate.not_valid_after_utc
    if expires_at < datetime.now(timezone.utc):
        raise ConfigurationError(
            f"Certificate expired at {expires_at.isoformat()}. Please obtain a new certificate."
        )

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "subject": certificate.subject.rfc4514_string(),
        "thumbprint": thumbprint,
        "expires_at": expires_at,
    }


def export_public_cert_base64(api_key: str) -> str:
    """Export the public certificate portion from a PFX as Base64.

    This matches the C# behavior: certificate.Export(X509ContentType.Cert) -> Base64

    Args:
        api_key: Base64-encoded PFX certificate

    Returns:
        Base64-encoded DER public certificate
    """
    normalized = api_key.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
    cert_bytes = base64.b64decode(normalized)

    certificate = None
    try:
        _, certificate, _ = pkcs12.load_key_and_certificates(cert_bytes, password=None)
    except Exception:
        try:
            certificate = x509.load_der_x509_certificate(cert_bytes)
        except Exception as e:
            raise ConfigurationError(f"Failed to parse certificate: {e}")

    if certificate is None:
        raise ConfigurationError("No certificate found in ApiKey")

    der_bytes = certificate.public_bytes(Encoding.DER)
    return base64.b64encode(der_bytes).decode("ascii")


def _get_subject_field(subject: x509.Name, oid: x509.ObjectIdentifier) -> Optional[str]:
    """Extract a single field from an X.509 subject by OID."""
    attrs = subject.get_attributes_for_oid(oid)
    return attrs[0].value if attrs else None
