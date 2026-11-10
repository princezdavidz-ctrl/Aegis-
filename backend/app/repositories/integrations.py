"""Tenant-scoped integration authorization registry persistence."""
from __future__ import annotations
from uuid import UUID
import json
from sqlalchemy import select,text
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker
from app.db.models import Integration

async def list_integrations(session: AsyncSession,tenant_id: UUID) -> list[Integration]:
    result=await session.execute(select(Integration).where(Integration.tenant_id==tenant_id).order_by(Integration.created_at.desc()))
    return list(result.scalars().all())

async def _call(factory: async_sessionmaker[AsyncSession],statement: str,params: dict[str,object]) -> dict[str,object]:
    async with factory() as session:
        row=(await session.execute(text(statement),params)).one()
        await session.commit()
        return {
            "id":row.integration_id,"tenant_id":row.integration_tenant_id,
            "provider":row.integration_provider,"display_name":row.integration_display_name,
            "external_account_id":row.integration_external_account_id,"status":row.integration_status,
            "access_mode":row.integration_access_mode,"requested_scopes":row.integration_requested_scopes,
            "approved_scopes":row.integration_approved_scopes,"created_by":row.integration_created_by,
            "approved_by":row.integration_approved_by,"approved_at":row.integration_approved_at,
            "created_at":row.integration_created_at,"updated_at":row.integration_updated_at,
        }

async def request_integration(factory: async_sessionmaker[AsyncSession],*,tenant_id: UUID,
    actor_subject: str,actor_type: str,request_id: UUID,provider: str,display_name: str,
    external_account_id: str | None,requested_scopes: list[str]) -> dict[str,object]:
    return await _call(factory,"""
        SELECT * FROM public.aegis_request_integration(
          :tenant_id,:actor_subject,:actor_type,:request_id,:provider,:display_name,
          :external_account_id,CAST(:requested_scopes AS json))
    """,{"tenant_id":tenant_id,"actor_subject":actor_subject,"actor_type":actor_type,
         "request_id":request_id,"provider":provider,"display_name":display_name,
         "external_account_id":external_account_id,"requested_scopes":json.dumps(requested_scopes)})

async def approve_integration(factory: async_sessionmaker[AsyncSession],*,tenant_id: UUID,
    integration_id: UUID,actor_subject: str,request_id: UUID,approved_scopes: list[str]) -> dict[str,object]:
    return await _call(factory,"""
        SELECT * FROM public.aegis_approve_integration(
          :tenant_id,:integration_id,:actor_subject,CAST(:approved_scopes AS json),:request_id)
    """,{"tenant_id":tenant_id,"integration_id":integration_id,"actor_subject":actor_subject,
         "request_id":request_id,"approved_scopes":json.dumps(approved_scopes)})

async def revoke_integration(factory: async_sessionmaker[AsyncSession],*,tenant_id: UUID,
    integration_id: UUID,actor_subject: str,request_id: UUID) -> dict[str,object]:
    return await _call(factory,"""
        SELECT * FROM public.aegis_revoke_integration(:tenant_id,:integration_id,:actor_subject,:request_id)
    """,{"tenant_id":tenant_id,"integration_id":integration_id,"actor_subject":actor_subject,"request_id":request_id})
