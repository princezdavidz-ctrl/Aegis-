"""PostgreSQL integration tests for asset tenant isolation and audit."""
from __future__ import annotations
import os
from uuid import uuid4
import pytest
from sqlalchemy import select,text
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.db.models import Asset,AuditRecord
from app.db.session import apply_database_context

ADMIN_URL=os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
RUNTIME_URL=os.getenv("AEGIS_TEST_DATABASE_URL")
PROVISIONER_URL=os.getenv("AEGIS_TEST_PROVISIONER_DATABASE_URL")
pytestmark=pytest.mark.skipif(not ADMIN_URL or not RUNTIME_URL or not PROVISIONER_URL,
    reason="PostgreSQL asset integration URLs are not configured")

@pytest.mark.asyncio
async def test_asset_inventory_is_tenant_isolated_and_audited() -> None:
    admin_engine=create_async_engine(ADMIN_URL)
    runtime_engine=create_async_engine(RUNTIME_URL)
    provisioner_engine=create_async_engine(PROVISIONER_URL)
    admin_factory=async_sessionmaker(admin_engine,expire_on_commit=False)
    runtime_factory=async_sessionmaker(runtime_engine,expire_on_commit=False)
    provisioner_factory=async_sessionmaker(provisioner_engine,expire_on_commit=False)
    actor="oidc|asset-admin"
    request_id=uuid4()
    slug_a=f"assets-a-{request_id.hex[:8]}"
    slug_b=f"assets-b-{request_id.hex[:8]}"
    try:
        async with provisioner_factory() as session:
            tenant_a=(await session.execute(text("""
                SELECT tenant_id FROM public.aegis_provision_tenant(
                    :slug,'Asset Tenant A',:actor,:actor,'user',:request_id)
            """),{"slug":slug_a,"actor":actor,"request_id":request_id})).scalar_one()
            tenant_b=(await session.execute(text("""
                SELECT tenant_id FROM public.aegis_provision_tenant(
                    :slug,'Asset Tenant B','oidc|other-admin','oidc|other-admin','user',:request_id)
            """),{"slug":slug_b,"request_id":uuid4()})).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            privileges=(await session.execute(text("""
                SELECT has_table_privilege(current_user,'assets','SELECT'),
                       has_table_privilege(current_user,'assets','INSERT'),
                       has_table_privilege(current_user,'assets','UPDATE')
            """))).one()
            assert privileges==(False,False,False)
            asset=(await session.execute(text("""
                SELECT asset_id,asset_name,asset_source,asset_status
                FROM public.aegis_create_asset(
                    :tenant_id,:actor,'user',:request_id,'Production API','application',
                    'svc-api-001','production','critical')
            """),{"tenant_id":tenant_a,"actor":actor,"request_id":uuid4()})).one()
            assert (asset.asset_name,asset.asset_source,asset.asset_status)==("Production API","manual","active")
            asset_id=asset.asset_id
            await session.commit()

        async with runtime_factory() as session:
            await apply_database_context(session,subject=actor,tenant_id=tenant_a)
            visible=(await session.execute(select(Asset).where(Asset.tenant_id==tenant_a))).scalars().all()
            assert len(visible)==1 and visible[0].id==asset_id
        async with runtime_factory() as session:
            # Even if a tenant UUID is mistakenly supplied, the RLS policy also
            # requires a persisted active membership for the verified subject.
            await apply_database_context(session,subject=actor,tenant_id=tenant_b)
            hidden=(await session.execute(select(Asset))).scalars().all()
            assert hidden==[]

        async with provisioner_factory() as session:
            updated=(await session.execute(text("""
                SELECT asset_name,asset_criticality,asset_status
                FROM public.aegis_update_asset(
                    :tenant_id,:asset_id,:actor,'user',:request_id,
                    'Production API v2',NULL,NULL,NULL,'high','active')
            """),{"tenant_id":tenant_a,"asset_id":asset_id,"actor":actor,"request_id":uuid4()})).one()
            assert (updated.asset_name,updated.asset_criticality,updated.asset_status)==(
                "Production API v2","high","active")
            await session.commit()

        async with provisioner_factory() as session:
            archived=(await session.execute(text("""
                SELECT asset_status FROM public.aegis_update_asset(
                    :tenant_id,:asset_id,:actor,'user',:request_id,
                    NULL,NULL,NULL,NULL,NULL,'archived')
            """),{"tenant_id":tenant_a,"asset_id":asset_id,"actor":actor,"request_id":uuid4()})).scalar_one()
            assert archived=="archived"
            await session.commit()

        async with admin_factory() as session:
            actions=(await session.execute(text("""
                SELECT action FROM audit_events
                WHERE tenant_id=:tenant_id AND resource_type='asset'
            """),{"tenant_id":tenant_a})).scalars().all()
            assert actions.count("asset.create")==1
            assert actions.count("asset.update")==1
            assert actions.count("asset.archive")==1
    finally:
        await provisioner_engine.dispose()
        await runtime_engine.dispose()
        await admin_engine.dispose()
