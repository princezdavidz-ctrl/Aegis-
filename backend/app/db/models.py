"""Tenant, membership, and immutable audit persistence models."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class MembershipStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"

class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
        CheckConstraint("data_retention_days BETWEEN 30 AND 3650", name="ck_tenants_data_retention_days"),
        CheckConstraint("policy_profile IN ('baseline', 'strict', 'regulated')", name="ck_tenants_policy_profile"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(80), nullable=True)
    organization_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90, server_default="90")
    policy_profile: Mapped[str] = mapped_column(String(32), nullable=False, default="baseline", server_default="baseline")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subject", name="uq_tenant_memberships_tenant_subject"),
        Index("ix_tenant_memberships_subject_status", "subject", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MembershipStatus.ACTIVE.value)
    invitation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_type", "external_id", name="uq_assets_tenant_type_external"),
        Index("ix_assets_tenant_status", "tenant_id", "status"),
        Index("ix_assets_tenant_criticality", "tenant_id", "criticality"),
        CheckConstraint("asset_type IN ('cloud_account','endpoint','server','domain','repository','network','application','database','user_identity','other')", name="ck_assets_type"),
        CheckConstraint("environment IN ('production','staging','development','test','unknown')", name="ck_assets_environment"),
        CheckConstraint("criticality IN ('critical','high','medium','low')", name="ck_assets_criticality"),
        CheckConstraint("source IN ('manual','integration')", name="ck_assets_source"),
        CheckConstraint("status IN ('active','archived')", name="ck_assets_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    environment: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    criticality: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", server_default="medium")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual", server_default="manual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class AuditRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_occurred", "tenant_id", "occurred_at"),
        Index("ix_audit_events_actor_occurred", "actor_subject", "occurred_at"),
    )
    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    authorization_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class EndpointDeviceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class EndpointEnrollmentInvitation(Base):
    """One-time tenant-bound endpoint enrollment invitation; digest only."""

    __tablename__ = "endpoint_enrollment_invitations"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_endpoint_invitation_token_digest"),
        Index("ix_endpoint_invites_tenant_expiry", "tenant_id", "expires_at"),
        CheckConstraint("platform IN ('windows', 'linux', 'macos')", name="ck_endpoint_invite_platform"),
        CheckConstraint("length(token_digest) = 64", name="ck_endpoint_invite_digest_length"),
        CheckConstraint("length(trim(created_by)) BETWEEN 1 AND 128", name="ck_endpoint_invite_creator"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class EndpointDevice(Base):
    """Tenant-bound endpoint public identity and replay/revocation state."""

    __tablename__ = "endpoint_devices"
    __table_args__ = (
        UniqueConstraint("public_key_fingerprint", name="uq_endpoint_device_key_fingerprint"),
        Index("ix_endpoint_devices_tenant_status", "tenant_id", "status"),
        Index("ix_endpoint_devices_tenant_last_seen", "tenant_id", "last_seen_at"),
        CheckConstraint("platform IN ('windows', 'linux', 'macos')", name="ck_endpoint_device_platform"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_endpoint_device_status"),
        CheckConstraint("last_sequence >= 0", name="ck_endpoint_device_sequence"),
        CheckConstraint("length(public_key_b64) BETWEEN 40 AND 64", name="ck_endpoint_device_public_key_length"),
        CheckConstraint("length(public_key_fingerprint) = 64", name="ck_endpoint_device_fingerprint_length"),
        CheckConstraint("length(trim(hostname)) BETWEEN 1 AND 255", name="ck_endpoint_device_hostname"),
        CheckConstraint("length(trim(agent_version)) BETWEEN 1 AND 64", name="ck_endpoint_device_agent_version"),
        UniqueConstraint("invitation_id", name="uq_endpoint_device_invitation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    invitation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("endpoint_enrollment_invitations.id", ondelete="RESTRICT"), nullable=False)
    public_key_b64: Mapped[str] = mapped_column(String(64), nullable=False)
    public_key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=EndpointDeviceStatus.ACTIVE.value)
    last_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
