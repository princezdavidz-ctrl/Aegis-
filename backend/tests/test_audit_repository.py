"""Tests for durable audit persistence and tenant binding."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AuditRecord, Tenant
from app.repositories.audit import PostgresAuditEventSink
from app.security.audit import AuditEvent, AuditOutcome
from app.security.authorization import AuthorizationReason
from app.security.identity import PrincipalType


@pytest.mark.asyncio
async def test_audit_sink_persists_minimal_event_with_tenant() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add(Tenant(id=tenant_id, slug="acme", display_name="Acme Ltd"))
            await session.commit()
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_subject="user-123",
            actor_type=PrincipalType.USER,
            action="investigation.read",
            resource_type="investigation",
            resource_id="case-123",
            outcome=AuditOutcome.AUTHORIZED,
            authorization_reason=AuthorizationReason.GRANTED,
        )
        sink = PostgresAuditEventSink(factory)
        await sink.append(event)
        async with factory() as session:
            record = (await session.execute(select(AuditRecord))).scalar_one()
        assert record.tenant_id == tenant_id
        assert record.actor_subject == "user-123"
        assert record.action == "investigation.read"
        assert not hasattr(sink, "update")
        assert not hasattr(sink, "delete")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audit_sink_rejects_missing_tenant_context() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        event = AuditEvent(
            actor_subject="user-123",
            actor_type=PrincipalType.USER,
            action="investigation.read",
            resource_type="investigation",
            resource_id="case-123",
            outcome=AuditOutcome.AUTHORIZED,
            authorization_reason=AuthorizationReason.GRANTED,
        )
        with pytest.raises(ValueError, match="tenant_id"):
            await PostgresAuditEventSink(factory).append(event)
    finally:
        await engine.dispose()
