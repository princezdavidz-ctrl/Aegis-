"""Provisioner-only repository calls for tenant-scoped webhook destinations."""
from __future__ import annotations

from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def create_webhook_destination(
    factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID, destination_id: UUID, actor: str,
    name: str, target_url: str, event_types: list[str], secret_ciphertext: bytes,
    secret_key_ref: str, secret_encryption_version: int = 1, secret_version: int = 1,
) -> dict[str, object]:
    async with factory() as session:
        row = (await session.execute(text("""
            SELECT * FROM public.aegis_webhook_create_destination_v2(
                :tenant_id, :destination_id, :actor, :name, :target_url, :event_types,
                :secret_ciphertext, :secret_key_ref,
                :secret_encryption_version, :secret_version
            )
        """), {
            "tenant_id": tenant_id, "destination_id": destination_id, "actor": actor, "name": name,
            "target_url": target_url, "event_types": event_types,
            "secret_ciphertext": secret_ciphertext, "secret_key_ref": secret_key_ref,
            "secret_encryption_version": secret_encryption_version,
            "secret_version": secret_version,
        })).one()
        await session.commit()
        return {
            "id": row.destination_id, "name": row.name, "target_url": row.target_url,
            "status": row.status, "event_types": row.event_types,
            "secret_version": row.secret_version, "created_at": row.created_at,
        }


async def list_webhook_destinations(
    factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID, actor: str,
) -> list[dict[str, object]]:
    async with factory() as session:
        rows = (await session.execute(text("""
            SELECT * FROM public.aegis_webhook_list_destinations(:tenant_id, :actor)
        """), {"tenant_id": tenant_id, "actor": actor})).all()
        return [{
            "id": row.destination_id, "name": row.name, "target_url": row.target_url,
            "status": row.status, "event_types": row.event_types,
            "secret_version": row.secret_version, "created_at": row.created_at,
            "updated_at": row.updated_at, "disabled_at": row.disabled_at,
        } for row in rows]


async def disable_webhook_destination(
    factory: async_sessionmaker[AsyncSession], *, tenant_id: UUID,
    destination_id: UUID, actor: str,
) -> bool:
    async with factory() as session:
        result = await session.execute(text("""
            SELECT public.aegis_webhook_disable_destination(
                :tenant_id, :destination_id, :actor
            )
        """), {"tenant_id": tenant_id, "destination_id": destination_id, "actor": actor})
        changed = bool(result.scalar_one())
        await session.commit()
        return changed
