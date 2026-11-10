"""Cryptographic primitives for endpoint enrollment and event authenticity.

Persistence, tenant binding, replay tracking and credential revocation belong to
the authenticated server-side device registry; these helpers do not replace it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.endpoint.schemas import EndpointTelemetryEnvelope

_ENROLLMENT_TOKEN_BYTES = 32
_ED25519_PUBLIC_KEY_BYTES = 32
_ED25519_SIGNATURE_BYTES = 64


def create_enrollment_token() -> tuple[str, str]:
    """Return a one-time high-entropy token and its SHA-256 storage digest.

    Store only the digest, never the raw token. The raw value should be shown
    once to an authorized tenant administrator and expire quickly.
    """
    token = secrets.token_urlsafe(_ENROLLMENT_TOKEN_BYTES)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, digest


def enrollment_token_matches(token: str, stored_digest: str) -> bool:
    """Constant-time comparison against a stored lowercase SHA-256 digest."""
    if not token or len(token) > 256 or len(stored_digest) != 64:
        return False
    candidate = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, stored_digest)


def canonical_event_bytes(event: EndpointTelemetryEnvelope) -> bytes:
    """Serialize the validated event deterministically for signature checks."""
    data: dict[str, Any] = event.model_dump(mode="json")
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def verify_endpoint_event_signature(
    event: EndpointTelemetryEnvelope,
    *,
    public_key_b64: str,
    signature_b64: str,
) -> bool:
    """Verify Ed25519 signature; malformed keys/signatures fail closed."""
    try:
        public_key = base64.b64decode(public_key_b64, validate=True)
        signature = base64.b64decode(signature_b64, validate=True)
        if len(public_key) != _ED25519_PUBLIC_KEY_BYTES:
            return False
        if len(signature) != _ED25519_SIGNATURE_BYTES:
            return False
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical_event_bytes(event)
        )
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False
