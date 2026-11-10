"""Live PostgreSQL row-level security and audit trigger integration tests.

Run after applying migrations and granting the aegis_runtime role the table
privileges in postgres_runtime_role.sql. These tests intentionally use separate
admin and restricted runtime connections.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import AuditRecord, Tenant, TenantMembership
from app.db.session import apply_database_context
from app.repositories.audit import PostgresAuditEventSink
from app.security.audit import AuditEvent, AuditOutcome
from app.security.authorization import AuthorizationReason
from app.security.identity import PrincipalType

ADMIN_URL = os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
RUNTIME_URL = os.getenv("AEGIS_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not ADMIN_URL or not RUNTIME_URL,
    reason="PostgreSQL integration URLs are not configured",
)


@pytest.mark.asyncio
async def test_postgres_rls_isolates_tenants_and_audit_is_append_only() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    runtime_engine = create_async_engine(RUNTIME_URL)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)

    tenant_a = uuid4()
    tenant_b = uuid4()
    membership_a = uuid4()
    membership_b = uuid4()
    audit_a = uuid4()
    audit_b = uuid4()

    try:
        # Seed as the database administrator, outside the restricted app role.
        async with admin_factory() as session:
            session.add_all(
                [
                    Tenant(id=tenant_a, slug=f"tenant-{tenant_a.hex[:8]}", display_name="Tenant A"),
                    Tenant(id=tenant_b, slug=f"tenant-{tenant_b.hex[:8]}", display_name="Tenant B"),
                    TenantMembership(
                        id=membership_a,
                        tenant_id=tenant_a,
                        subject="subject-a",
                        role="analyst",
                        status="active",
                    ),
                    TenantMembership(
                        id=membership_b,
                        tenant_id=tenant_b,
                        subject="subject-b",
                        role="analyst",
                        status="active",
                    ),
                    AuditRecord(
                        event_id=audit_a,
                        tenant_id=tenant_a,
                        occurred_at=datetime.now(timezone.utc),
                        actor_subject="subject-a",
                        actor_type="user",
                        action="seed.event",
                        resource_type="test",
                        resource_id="tenant-a",
                        outcome="succeeded",
                        authorization_reason="granted",
                    ),
                    AuditRecord(
                        event_id=audit_b,
                        tenant_id=tenant_b,
                        occurred_at=datetime.now(timezone.utc),
                        actor_subject="subject-b",
                        actor_type="user",
                        action="seed.event",
                        resource_type="test",
                        resource_id="tenant-b",
                        outcome="succeeded",
                        authorization_reason="granted",
                    ),
                ]
            )
            await session.commit()

        # Runtime identity can see only its own tenant and membership.
        async with runtime_factory() as session:
            await apply_database_context(session, subject="subject-a")
            visible_tenants = (await session.execute(select(Tenant.slug))).scalars().all()
            visible_memberships = (
                await session.execute(select(TenantMembership.subject))
            ).scalars().all()
            assert len(visible_tenants) == 1
            assert visible_tenants[0].startswith("tenant-")
            assert visible_memberships == ["subject-a"]

        # Audit visibility is restricted to the active transaction's tenant.
        async with runtime_factory() as session:
            await apply_database_context(session, subject="subject-a", tenant_id=tenant_a)
            visible_audits = (
                await session.execute(select(AuditRecord.event_id))
            ).scalars().all()
            assert visible_audits == [audit_a]

        # The production adapter can append for the server-resolved tenant.
        event = AuditEvent(
            tenant_id=tenant_a,
            actor_subject="subject-a",
            actor_type=PrincipalType.USER,
            action="investigation.read",
            resource_type="investigation",
            resource_id="case-a",
            outcome=AuditOutcome.SUCCEEDED,
            authorization_reason=AuthorizationReason.GRANTED,
        )
        await PostgresAuditEventSink(runtime_factory).append(event)

        # RLS rejects writing a different tenant's audit row.
        async with runtime_factory() as session:
            await apply_database_context(session, subject="subject-a", tenant_id=tenant_a)
            with pytest.raises(DBAPIError):
                await session.execute(
                    text(
                        """
                        INSERT INTO audit_events (
                            event_id, tenant_id, occurred_at, actor_subject,
                            actor_type, action, resource_type, resource_id,
                            outcome, authorization_reason
                        ) VALUES (
                            :event_id, :tenant_id, :occurred_at, 'subject-a',
                            'user', 'cross.tenant.write', 'test', 'denied',
                            'succeeded', 'granted'
                        )
                        """
                    ),
                    {
                        "event_id": str(uuid4()),
                        "tenant_id": str(tenant_b),
                        "occurred_at": datetime.now(timezone.utc),
                    },
                )
            await session.rollback()

        # The database trigger rejects UPDATE and DELETE even for the owning tenant.
        async with runtime_factory() as session:
            await apply_database_context(session, subject="subject-a", tenant_id=tenant_a)
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE audit_events SET action = 'tampered' WHERE event_id = :id"),
                    {"id": str(audit_a)},
                )
            await session.rollback()

        async with runtime_factory() as session:
            await apply_database_context(session, subject="subject-a", tenant_id=tenant_a)
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("DELETE FROM audit_events WHERE event_id = :id"),
                    {"id": str(audit_a)},
                )
            await session.rollback()
    finally:
        # Remove test rows with the administrative connection after assertions.
        async with admin_factory() as session:
            await session.execute(
                text("DELETE FROM audit_events WHERE tenant_id IN (:a, :b)"),
                {"a": str(tenant_a), "b": str(tenant_b)},
            )
            await session.execute(
                text("DELETE FROM tenant_memberships WHERE tenant_id IN (:a, :b)"),
                {"a": str(tenant_a), "b": str(tenant_b)},
            )
            await session.execute(
                text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                {"a": str(tenant_a), "b": str(tenant_b)},
            )
            await session.commit()
        await runtime_engine.dispose()
        await admin_engine.dispose()
