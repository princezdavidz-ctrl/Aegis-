"""Tests for endpoint enrollment token and Ed25519 event signatures."""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.endpoint.identity import (
    canonical_event_bytes,
    create_enrollment_token,
    enrollment_token_matches,
    verify_endpoint_event_signature,
)
from app.endpoint.schemas import EndpointEventType, EndpointTelemetryEnvelope


def event():
    from uuid import uuid4
    return EndpointTelemetryEnvelope(
        device_id=uuid4(),
        event_id=uuid4(),
        sequence=4,
        observed_at="2026-11-10T12:00:00Z",
        event_type=EndpointEventType.HEARTBEAT,
        payload={"status": "healthy"},
    )


def keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, base64.b64encode(public_key).decode("ascii")


def test_enrollment_token_is_high_entropy_and_only_digest_is_returned():
    token, digest = create_enrollment_token()
    assert len(token) >= 40
    assert len(digest) == 64
    assert token not in digest
    assert enrollment_token_matches(token, digest)


def test_enrollment_token_rejects_wrong_token_and_malformed_digest():
    token, digest = create_enrollment_token()
    assert not enrollment_token_matches(token + "x", digest)
    assert not enrollment_token_matches(token, "bad")


def test_ed25519_signature_verifies_for_canonical_event():
    item = event()
    private_key, public_key = keypair()
    signature = base64.b64encode(private_key.sign(canonical_event_bytes(item))).decode("ascii")
    assert verify_endpoint_event_signature(
        item, public_key_b64=public_key, signature_b64=signature
    )


def test_signature_fails_when_event_payload_changes():
    item = event()
    private_key, public_key = keypair()
    signature = base64.b64encode(private_key.sign(canonical_event_bytes(item))).decode("ascii")
    changed = item.model_copy(update={"payload": {"status": "tampered"}})
    assert not verify_endpoint_event_signature(
        changed, public_key_b64=public_key, signature_b64=signature
    )


def test_signature_rejects_wrong_key():
    item = event()
    signer, _ = keypair()
    _, other_public = keypair()
    signature = base64.b64encode(signer.sign(canonical_event_bytes(item))).decode("ascii")
    assert not verify_endpoint_event_signature(
        item, public_key_b64=other_public, signature_b64=signature
    )


def test_signature_rejects_malformed_inputs():
    item = event()
    assert not verify_endpoint_event_signature(
        item, public_key_b64="not-base64!", signature_b64="not-base64!"
    )
