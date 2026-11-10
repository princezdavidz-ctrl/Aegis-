"""Contract tests for endpoint registry ORM metadata."""

from app.db.models import EndpointDevice, EndpointEnrollmentInvitation


def test_endpoint_registry_models_are_tenant_bound_and_store_only_token_digest():
    invite_columns = set(EndpointEnrollmentInvitation.__table__.columns.keys())
    device_columns = set(EndpointDevice.__table__.columns.keys())
    assert {"tenant_id", "token_digest", "expires_at", "consumed_at"} <= invite_columns
    assert "raw_token" not in invite_columns
    assert {"tenant_id", "public_key_fingerprint", "last_sequence", "status", "revoked_at"} <= device_columns


def test_endpoint_registry_has_unique_identity_and_replay_constraints():
    invite_constraints = {c.name for c in EndpointEnrollmentInvitation.__table__.constraints}
    device_constraints = {c.name for c in EndpointDevice.__table__.constraints}
    assert "uq_endpoint_invitation_token_digest" in invite_constraints
    assert "uq_endpoint_device_key_fingerprint" in device_constraints
    assert any("last_sequence" in str(c.sqltext) for c in EndpointDevice.__table__.constraints if hasattr(c, "sqltext"))
