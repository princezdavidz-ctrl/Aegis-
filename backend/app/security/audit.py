"""Minimal append-only audit event contract; durable adapters are injected."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.security.authorization import AuthorizationReason
from app.security.identity import PrincipalType


class AuditOutcome(StrEnum):
    AUTHORIZED = "authorized"
    DENIED = "denied"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AuditEvent(BaseModel):
    """Immutable, payload-free event for an authorization or action outcome.

    Identifiers are opaque references, not places for names, credentials, URLs,
    request bodies, command output, or other sensitive data. Tenant binding is
    required by durable persistence adapters.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_subject: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:@|/-]{0,127}$",
    )
    actor_type: PrincipalType
    action: str = Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_.:-]{0,95}$")
    resource_type: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_.:-]{0,63}$")
    resource_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    outcome: AuditOutcome
    authorization_reason: AuthorizationReason
    correlation_id: UUID | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_aware_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_authorization_outcome(self) -> AuditEvent:
        if self.outcome == AuditOutcome.DENIED:
            if self.authorization_reason == AuthorizationReason.GRANTED:
                raise ValueError("a denied event cannot have a granted authorization reason")
        elif self.authorization_reason != AuthorizationReason.GRANTED:
            raise ValueError("non-denied events require a granted authorization reason")
        return self


@runtime_checkable
class AuditEventSink(Protocol):
    """Append-only persistence boundary; implementations must never update/delete.

    Production adapters must provide durable writes and fail closed when an
    event cannot be persisted. A tenant-bound durable adapter must reject events
    without a server-resolved tenant ID.
    """

    async def append(self, event: AuditEvent, /) -> None:
        """Persist one immutable event without exposing mutation operations."""
        ...
