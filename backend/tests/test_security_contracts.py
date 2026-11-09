"""Tests for deny-by-default identity, authorization, and audit contracts."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.security.audit import AuditEvent, AuditEventSink, AuditOutcome
from app.security.authorization import AuthorizationDecision, AuthorizationReason, authorize
from app.security.identity import Permission, Principal, PrincipalType


def test_missing_principal_is_denied() -> None:
    decision = authorize(None, Permission.TOOL_EXECUTE)
    assert decision.allowed is False
    assert decision.reason == AuthorizationReason.MISSING_PRINCIPAL
    assert decision.subject is None


def test_principal_without_scopes_is_denied_by_default() -> None:
    principal = Principal(subject="user-123", principal_type=PrincipalType.USER)
    decision = authorize(principal, Permission.INVESTIGATION_READ)
    assert decision.allowed is False
    assert decision.reason == AuthorizationReason.MISSING_SCOPE
    assert decision.subject == "user-123"


def test_exact_declared_scope_is_granted() -> None:
    principal = Principal(
        subject="service-a",
        principal_type=PrincipalType.SERVICE,
        scopes=frozenset({Permission.TELEMETRY_READ}),
    )
    decision = authorize(principal, Permission.TELEMETRY_READ)
    assert decision.allowed is True
    assert decision.reason == AuthorizationReason.GRANTED


def test_scopes_do_not_imply_other_permissions() -> None:
    principal = Principal(
        subject="service-a",
        principal_type=PrincipalType.SERVICE,
        scopes=frozenset({Permission.TELEMETRY_READ}),
    )
    assert not authorize(principal, Permission.TOOL_EXECUTE).allowed


def test_wildcard_and_unknown_scopes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Principal(subject="admin", principal_type=PrincipalType.USER, scopes={"*"})
    with pytest.raises(ValidationError):
        Principal(subject="admin", principal_type=PrincipalType.USER, scopes={"admin:all"})


def test_principal_is_immutable_and_rejects_extra_fields() -> None:
    principal = Principal(subject="  user-1  ", principal_type=PrincipalType.USER)
    assert principal.subject == "user-1"
    with pytest.raises(ValidationError):
        principal.subject = "user-2"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Principal(subject="user-1", principal_type=PrincipalType.USER, is_admin=True)


def test_audit_event_defaults_to_utc_and_is_immutable() -> None:
    event = AuditEvent(
        actor_subject="user-123",
        actor_type=PrincipalType.USER,
        action="investigation.read",
        resource_type="investigation",
        resource_id="case-123",
        outcome=AuditOutcome.AUTHORIZED,
        authorization_reason=AuthorizationReason.GRANTED,
    )
    assert isinstance(event.event_id, UUID)
    assert event.occurred_at.utcoffset() == timedelta(0)
    with pytest.raises(ValidationError):
        event.resource_id = "case-456"  # type: ignore[misc]


def test_audit_event_normalizes_aware_timestamp_to_utc() -> None:
    local_time = datetime(2026, 11, 8, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    event = AuditEvent(
        occurred_at=local_time,
        actor_subject="user-123",
        actor_type=PrincipalType.USER,
        action="investigation.read",
        resource_type="investigation",
        resource_id="case-123",
        outcome=AuditOutcome.AUTHORIZED,
        authorization_reason=AuthorizationReason.GRANTED,
    )
    assert event.occurred_at.hour == 9
    assert event.occurred_at.utcoffset() == timedelta(0)


def test_audit_event_rejects_naive_timestamps_and_extra_payload_fields() -> None:
    common = {
        "actor_subject": "user-123",
        "actor_type": PrincipalType.USER,
        "action": "investigation.read",
        "resource_type": "investigation",
        "resource_id": "case-123",
        "outcome": AuditOutcome.AUTHORIZED,
        "authorization_reason": AuthorizationReason.GRANTED,
    }
    with pytest.raises(ValidationError):
        AuditEvent(**common, occurred_at=datetime(2026, 11, 8, 12, 0))
    with pytest.raises(ValidationError):
        AuditEvent(**common, request_body="sensitive payload")


def test_audit_event_enforces_outcome_and_authorization_consistency() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            actor_subject="user-123",
            actor_type=PrincipalType.USER,
            action="tool.execute",
            resource_type="tool",
            resource_id="scanner-1",
            outcome=AuditOutcome.DENIED,
            authorization_reason=AuthorizationReason.GRANTED,
        )


def test_audit_event_sink_exposes_only_append() -> None:
    class RecordingSink:
        async def append(self, event: AuditEvent, /) -> None:
            self.last_event = event

    assert isinstance(RecordingSink(), AuditEventSink)
    assert set(AuditEventSink.__dict__).intersection({"append", "update", "delete"}) == {"append"}


def test_authorization_decision_rejects_inconsistent_claims() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(
            allowed=True,
            required_scope=Permission.TOOL_EXECUTE,
            reason=AuthorizationReason.MISSING_SCOPE,
            subject="user-1",
        )
