"""Contract tests for the endpoint agent telemetry boundary."""
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.endpoint.schemas import EndpointAgentDescriptor, EndpointEventType, EndpointPlatform, EndpointTelemetryEnvelope

def descriptor(**overrides):
    values = {"agent_version":"0.1.0","platform":EndpointPlatform.LINUX,"platform_version":"Ubuntu 24.04","architecture":"x86_64","hostname":"workstation-01","collection_profile":"standard"}
    return EndpointAgentDescriptor(**(values | overrides))

def envelope(**overrides):
    values = {"device_id":uuid4(),"event_id":uuid4(),"sequence":1,"observed_at":"2026-11-10T12:00:00Z","event_type":EndpointEventType.HEARTBEAT,"payload":{"agent_status":"healthy"}}
    return EndpointTelemetryEnvelope(**(values | overrides))

def test_accepts_supported_os_descriptors():
    for platform in EndpointPlatform:
        assert descriptor(platform=platform).platform is platform

def test_rejects_unknown_descriptor_fields():
    with pytest.raises(ValidationError): descriptor(remote_shell=True)

def test_rejects_control_characters_in_metadata():
    with pytest.raises(ValidationError): descriptor(hostname="host\nforged")

def test_normalizes_timezone_aware_timestamps_to_utc():
    assert envelope(observed_at="2026-11-10T15:00:00+03:00").observed_at.isoformat() == "2026-11-10T12:00:00+00:00"

def test_rejects_naive_timestamps():
    with pytest.raises(ValidationError): envelope(observed_at=datetime(2026,11,10,12,0))

def test_rejects_client_supplied_tenant_identity():
    with pytest.raises(ValidationError): envelope(tenant_id=str(uuid4()))

def test_rejects_unknown_event_types():
    with pytest.raises(ValidationError): envelope(event_type="arbitrary_command")

def test_rejects_invalid_sequence():
    with pytest.raises(ValidationError): envelope(sequence=0)

def test_rejects_oversized_payloads():
    with pytest.raises(ValidationError): envelope(payload={"data":"x"*33000})

def test_rejects_non_finite_json_values():
    with pytest.raises(ValidationError): envelope(payload={"score":float("nan")})

def test_schema_version_is_pinned():
    with pytest.raises(ValidationError): envelope(schema_version=2)