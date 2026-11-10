"""Tenant profile persistence and controlled update calls."""
from __future__ import annotations
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.models import Tenant

async def get_tenant_profile(session: AsyncSession, tenant_id: UUID) -> Tenant | None:
    return await session.get(Tenant, tenant_id)

async def update_tenant_profile(factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID,
    actor_subject: str, actor_type: str, request_id: UUID, industry: str | None,
    organization_size: str | None, region: str | None, data_retention_days: int | None,
    policy_profile: str | None) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
            SELECT tenant_id, tenant_slug, tenant_display_name, tenant_industry,
                   tenant_organization_size, tenant_region, tenant_data_retention_days,
                   tenant_policy_profile, tenant_created_at
            FROM public.aegis_update_tenant_profile(
              :tenant_id,:actor_subject,:actor_type,:request_id,:industry,
              :organization_size,:region,:data_retention_days,:policy_profile
            )
        """), {
            "tenant_id":tenant_id, "actor_subject":actor_subject, "actor_type":actor_type,
            "request_id":request_id, "industry":industry, "organization_size":organization_size,
            "region":region, "data_retention_days":data_retention_days, "policy_profile":policy_profile,
        })).one()
        await session.commit()
        return {
            "id":row.tenant_id, "slug":row.tenant_slug, "display_name":row.tenant_display_name,
            "industry":row.tenant_industry, "organization_size":row.tenant_organization_size,
            "region":row.tenant_region, "data_retention_days":row.tenant_data_retention_days,
            "policy_profile":row.tenant_policy_profile, "created_at":row.tenant_created_at,
        }
