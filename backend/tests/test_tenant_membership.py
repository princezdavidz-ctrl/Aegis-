"""Tenant membership resolution tests using isolated SQLite databases."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import MembershipStatus, Tenant, TenantMembership
from app.repositories.tenants import resolve_active_membership


@pytest.mark.asyncio
async def test_membership_resolves_tenant_from_verified_subject_and_slug() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        tenant_id = uuid4()
        membership_id = uuid4()
        async with factory() as session:
            session.add(Tenant(id=tenant_id, slug="acme", display_name="Acme Ltd"))
            session.add(TenantMembership(
                id=membership_id,
                tenant_id=tenant_id,
                subject="oidc|user-123",
                role="analyst",
                status=MembershipStatus.ACTIVE.value,
            ))
            await session.commit()
        async with factory() as session:
            result = await resolve_active_membership(
                session, subject="oidc|user-123", tenant_slug="acme"
            )
        assert result == (tenant_id, membership_id, "acme", "analyst")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_membership_denies_other_tenant_or_subject() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        tenant_id = uuid4()
        async with factory() as session:
            session.add(Tenant(id=tenant_id, slug="acme", display_name="Acme Ltd"))
            session.add(TenantMembership(
                tenant_id=tenant_id,
                subject="user-a",
                role="admin",
                status=MembershipStatus.ACTIVE.value,
            ))
            await session.commit()
        async with factory() as session:
            assert await resolve_active_membership(
                session, subject="user-b", tenant_slug="acme"
            ) is None
            assert await resolve_active_membership(
                session, subject="user-a", tenant_slug="other"
            ) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_suspended_membership_is_denied() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        tenant_id = uuid4()
        async with factory() as session:
            session.add(Tenant(id=tenant_id, slug="acme", display_name="Acme Ltd"))
            session.add(TenantMembership(
                tenant_id=tenant_id,
                subject="user-a",
                role="admin",
                status=MembershipStatus.SUSPENDED.value,
            ))
            await session.commit()
        async with factory() as session:
            assert await resolve_active_membership(
                session, subject="user-a", tenant_slug="acme"
            ) is None
    finally:
        await engine.dispose()
