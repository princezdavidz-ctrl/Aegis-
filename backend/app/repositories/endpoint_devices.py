"""Narrow database-function boundary for endpoint lifecycle operations."""
from __future__ import annotations

from datetime import datetime
import json
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def create_invitation(factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID,
    actor: str, actor_type: str, request_id: UUID, digest: str, platform: str,
    expires_at: datetime) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
          SELECT invitation_id,tenant_id,platform,expires_at
          FROM public.aegis_endpoint_create_invitation(
            :tenant_id,:actor,:actor_type,:request_id,:digest,:platform,:expires_at)
        """), {"tenant_id":tenant_id,"actor":actor,"actor_type":actor_type,
          "request_id":request_id,"digest":digest,"platform":platform,"expires_at":expires_at})).one()
        await session.commit()
        return {"id":row.invitation_id,"tenant_id":row.tenant_id,
          "platform":row.platform,"expires_at":row.expires_at}


async def redeem_invitation(factory: async_sessionmaker[AsyncSession], *, digest: str,
    platform: str, public_key_b64: str, fingerprint: str, hostname: str,
    agent_version: str) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
          SELECT device_id,tenant_id,platform,hostname,agent_version
          FROM public.aegis_endpoint_redeem_invitation(
            :digest,:platform,:public_key_b64,:fingerprint,:hostname,:agent_version)
        """), {"digest":digest,"platform":platform,"public_key_b64":public_key_b64,
          "fingerprint":fingerprint,"hostname":hostname,"agent_version":agent_version})).one()
        await session.commit()
        return {"id":row.device_id,"tenant_id":row.tenant_id,"platform":row.platform,
          "hostname":row.hostname,"agent_version":row.agent_version}


async def get_active_device_key(factory: async_sessionmaker[AsyncSession], *,
    device_id: UUID) -> dict[str, object] | None:
    async with factory() as session:
        row = (await session.execute(text("""
          SELECT device_id,tenant_id,public_key_b64,status
          FROM public.aegis_endpoint_get_active_key(:device_id)
        """), {"device_id":device_id})).one_or_none()
        return None if row is None else {"id":row.device_id,"tenant_id":row.tenant_id,
          "public_key_b64":row.public_key_b64,"status":row.status}


async def accept_event(factory: async_sessionmaker[AsyncSession], *, device_id: UUID,
    sequence: int, event_id: UUID, event_type: str, observed_at: datetime,
    payload: dict[str, object]) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
          SELECT device_id,tenant_id,event_id,sequence,received_at
          FROM public.aegis_endpoint_accept_event(
            :device_id,:sequence,:event_id,:event_type,:observed_at,CAST(:payload AS jsonb))
        """), {"device_id":device_id,"sequence":sequence,"event_id":event_id,
          "event_type":event_type,"observed_at":observed_at,
          "payload":json.dumps(payload,separators=(",",":"),allow_nan=False)})).one()
        await session.commit()
        return {"device_id":row.device_id,"tenant_id":row.tenant_id,
          "event_id":row.event_id,"sequence":row.sequence,"received_at":row.received_at}


async def revoke_device(factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID,
    device_id: UUID, actor: str, actor_type: str, request_id: UUID) -> None:
    async with factory() as session:
        await session.execute(text("""
          SELECT public.aegis_endpoint_revoke_device(
            :tenant_id,:device_id,:actor,:actor_type,:request_id)
        """), {"tenant_id":tenant_id,"device_id":device_id,"actor":actor,
          "actor_type":actor_type,"request_id":request_id})
        await session.commit()
