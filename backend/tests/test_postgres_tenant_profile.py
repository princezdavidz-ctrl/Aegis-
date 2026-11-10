"""PostgreSQL integration test for tenant profile read/write boundaries."""
from __future__ import annotations
import os
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.models import AuditRecord, Tenant
from app.db.session import apply_database_context

ADMIN_URL = os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
RUNTIME_URL = os.getenv("AEGIS_TEST_DATABASE_URL")
PROVISIONER_URL = os.getenv("AEGIS_TEST_PROVISIONER_DATABASE_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL or not RUNTIME_URL or not PROVISIONER_URL,
    reason="PostgreSQL profile integration URLs are not configured")

@pytest.mark.asyncio
async def test_tenant_profile_is_tenant_scoped_admin_writable_and_audited() -> None:
    admin_engine=create_async_engine(ADMIN_URL)
    runtime_engine=create_async_engine(RUNTIME_URL)
    provisioner_engine=create_async_engine(PROVISIONER_URL)
    admin_factory=async_sessionmaker(admin_engine,expire_on_commit=False)
    runtime_factory=async_sessionmaker(runtime_engine,expire_on_commit=False)
    provisioner_factory=async_sessionmaker(provisioner_engine,expire_on_commit=False)
    actor="oidc|profile-admin"
    request_id=uuid4()
    slug=f"profile-{request_id.hex[:10]}"
    try:
        async with provisioner_factory() as session:
            tenant_id=(await session.execute(text("""
                SELECT tenant_id FROM public.aegis_provision_tenant(
                    :slug,'Profile Test',:actor,:actor,'user',:request_id)
            """),{"slug":slug,"actor":actor,"request_id":request_id})).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            updated=(await session.execute(text("""
                SELECT tenant_slug,tenant_industry,tenant_organization_size,tenant_region,
                       tenant_data_retention_days,tenant_policy_profile
                FROM public.aegis_update_tenant_profile(
                    :tenant_id,:actor,'user',:request_id,:industry,:size,:region,:retention,:policy)
            """),{
                "tenant_id":tenant_id,"actor":actor,"request_id":uuid4(),
                "industry":"Healthcare","size":"51-200","region":"Africa",
                "retention":365,"policy":"regulated",
            })).one()
            assert updated.tenant_slug==slug
            assert updated.tenant_industry=="Healthcare"
            assert updated.tenant_organization_size=="51-200"
            assert updated.tenant_region=="Africa"
            assert updated.tenant_data_retention_days==365
            assert updated.tenant_policy_profile=="regulated"
            await session.commit()

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT * FROM public.aegis_update_tenant_profile(
                        :tenant_id,'oidc|not-admin','user',:request_id,
                        'Retail',NULL,NULL,NULL,NULL)
                """),{"tenant_id":tenant_id,"request_id":uuid4()})
            await session.rollback()

        async with runtime_factory() as session:
            await apply_database_context(session,subject=actor,tenant_id=tenant_id)
            tenant=await session.get(Tenant,tenant_id)
            assert tenant is not None
            assert tenant.industry=="Healthcare"
            assert tenant.policy_profile=="regulated"

        async with admin_factory() as session:
            audit=(await session.execute(select(AuditRecord).where(
                AuditRecord.tenant_id==tenant_id,
                AuditRecord.action=="tenant.profile.update"
            ))).scalar_one()
            assert audit.actor_subject==actor
            assert audit.outcome=="succeeded"
    finally:
        await provisioner_engine.dispose()
        await runtime_engine.dispose()
        await admin_engine.dispose()
