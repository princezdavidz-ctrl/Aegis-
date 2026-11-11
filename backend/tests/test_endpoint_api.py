"""Tests for endpoint lifecycle request contracts and fail-closed routing."""
import base64
from uuid import uuid4

import pytest
from pydantic import ValidationError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.api.endpoints import EnrollmentInput, InvitationInput, SignedEventInput
from app.endpoint.identity import canonical_event_bytes
from app.endpoint.schemas import EndpointEventType, EndpointPlatform, EndpointTelemetryEnvelope


def test_invitation_contract_limits_ttl_and_rejects_extra_fields():
    assert InvitationInput(platform=EndpointPlatform.LINUX, ttl_minutes=60).ttl_minutes == 60
    with pytest.raises(ValidationError):
        InvitationInput(platform=EndpointPlatform.LINUX, ttl_minutes=1441)
    with pytest.raises(ValidationError):
        InvitationInput(platform=EndpointPlatform.LINUX, tenant_id=str(uuid4()))


def test_enrollment_contract_rejects_invalid_platform_and_metadata():
    with pytest.raises(ValidationError):
        EnrollmentInput(enrollment_token="x" * 40, platform="freebsd",
            public_key_b64="A" * 44, hostname="host", agent_version="1.0")
    with pytest.raises(ValidationError):
        EnrollmentInput(enrollment_token="x" * 40, platform="linux",
            public_key_b64="A" * 44, hostname="bad\nhost", agent_version="1.0")


def test_enrollment_public_key_must_be_ed25519_sized_at_api_boundary():
    with pytest.raises(ValidationError):
        EnrollmentInput(enrollment_token="x" * 40, platform="linux",
            public_key_b64=base64.b64encode(b"x" * 16).decode(),
            hostname="host", agent_version="1.0")


def test_signed_event_wrapper_requires_signature_and_rejects_tenant_override():
    event = EndpointTelemetryEnvelope(device_id=uuid4(), event_id=uuid4(), sequence=1,
        observed_at="2026-11-11T12:00:00Z", event_type=EndpointEventType.HEARTBEAT,
        payload={"status":"healthy"})
    private = Ed25519PrivateKey.generate()
    signature = base64.b64encode(private.sign(canonical_event_bytes(event))).decode()
    assert SignedEventInput(event=event, signature_b64=signature).event.sequence == 1
    with pytest.raises(ValidationError):
        SignedEventInput(event=event, signature_b64=signature, tenant_id=str(uuid4()))


def test_signed_event_contract_rejects_short_signature():
    event = EndpointTelemetryEnvelope(device_id=uuid4(), event_id=uuid4(), sequence=1,
        observed_at="2026-11-11T12:00:00Z", event_type=EndpointEventType.HEARTBEAT,
        payload={})
    with pytest.raises(ValidationError):
        SignedEventInput(event=event, signature_b64="short")


def test_fleet_response_contract_is_tenant_agnostic_and_includes_health_metadata():
    from app.api.endpoints import EndpointDeviceSummary, EndpointFleetOutput
    row = EndpointDeviceSummary(
        device_id=uuid4(), platform="linux", hostname="sensor-01", agent_version="0.1.0",
        status="active", enrolled_at="2026-11-11T12:00:00Z", last_seen_at=None,
        last_sequence=0, revoked_at=None, last_event_type=None, last_event_received_at=None,
    )
    response = EndpointFleetOutput(items=[row], limit=100)
    assert response.items[0].hostname == "sensor-01"
    assert response.items[0].last_seen_at is None
    with pytest.raises(ValidationError):
        EndpointDeviceSummary(
            device_id=uuid4(), platform="linux", hostname="sensor-01", agent_version="0.1.0",
            status="active", enrolled_at="2026-11-11T12:00:00Z", last_seen_at=None,
            last_sequence=0, revoked_at=None, last_event_type=None, last_event_received_at=None,
            tenant_id=uuid4(),
        )
