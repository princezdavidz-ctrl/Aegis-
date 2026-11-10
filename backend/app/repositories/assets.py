"""Tenant-scoped asset inventory persistence."""
from __future__ import annotations
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.models import Asset

async def list_assets(session: AsyncSession, tenant_id: UUID, *, include_archived: bool, limit: int, offset: int) -> list[Asset]:
    query = select(Asset).where(Asset.tenant_id == tenant_id)
    if not include_archived:
        query = query.where(Asset.status == "active")
    rows = await session.execute(query.order_by(Asset.created_at.desc()).limit(limit).offset(offset))
    return list(rows.scalars().all())

async def create_asset(factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID, actor_subject: str,
    actor_type: str, request_id: UUID, name: str, asset_type: str, external_id: str | None,
    environment: str, criticality: str) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
            SELECT asset_id,asset_tenant_id,asset_name,asset_type,asset_external_id,
              asset_environment,asset_criticality,asset_source,asset_status,asset_created_at,asset_updated_at
            FROM public.aegis_create_asset(:tenant_id,:actor_subject,:actor_type,:request_id,
              :name,:asset_type,:external_id,:environment,:criticality)
        """), {
            "tenant_id":tenant_id,"actor_subject":actor_subject,"actor_type":actor_type,
            "request_id":request_id,"name":name,"asset_type":asset_type,
            "external_id":external_id,"environment":environment,"criticality":criticality,
        })).one()
        await session.commit()
        return _asset_dict(row)

async def update_asset(factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID, asset_id: UUID,
    actor_subject: str, actor_type: str, request_id: UUID, name: str | None,
    asset_type: str | None, external_id: str | None, environment: str | None,
    criticality: str | None, status: str | None) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
            SELECT asset_id,asset_tenant_id,asset_name,asset_type,asset_external_id,
              asset_environment,asset_criticality,asset_source,asset_status,asset_created_at,asset_updated_at
            FROM public.aegis_update_asset(:tenant_id,:asset_id,:actor_subject,:actor_type,:request_id,
              :name,:asset_type,:external_id,:environment,:criticality,:status)
        """), {
            "tenant_id":tenant_id,"asset_id":asset_id,"actor_subject":actor_subject,
            "actor_type":actor_type,"request_id":request_id,"name":name,"asset_type":asset_type,
            "external_id":external_id,"environment":environment,"criticality":criticality,"status":status,
        })).one()
        await session.commit()
        return _asset_dict(row)

def _asset_dict(row) -> dict[str, object]:
    return {
        "id":row.asset_id,"tenant_id":row.asset_tenant_id,"name":row.asset_name,
        "asset_type":row.asset_type,"external_id":row.asset_external_id,
        "environment":row.asset_environment,"criticality":row.asset_criticality,
        "source":row.asset_source,"status":row.asset_status,
        "created_at":row.asset_created_at,"updated_at":row.asset_updated_at,
    }
