"""Tenant membership lifecycle database operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def list_members(
    factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: UUID,
    actor_subject: str,
) -> list[dict[str, object]]:
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT member_id, member_subject, member_role,
                           member_status, member_created_at, member_invitation_expires_at
                    FROM public.aegis_list_tenant_members(:tenant_id, :actor_subject)
                    """
                ),
                {"tenant_id": tenant_id, "actor_subject": actor_subject},
            )
        ).all()
        return [
            {
                "id": row.member_id,
                "subject": row.member_subject,
                "role": row.member_role,
                "status": row.member_status,
                "created_at": row.member_created_at,
                "invitation_expires_at": row.member_invitation_expires_at,
            }
            for row in rows
        ]


async def manage_member(
    factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: UUID,
    target_subject: str,
    target_role: str | None,
    action: str,
    actor_subject: str,
    actor_type: str,
    request_id: UUID,
) -> dict[str, object]:
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT member_id, member_subject, member_role, member_status
                    FROM public.aegis_manage_tenant_member(
                        :tenant_id, :target_subject, :target_role, :action,
                        :actor_subject, :actor_type, :request_id
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "target_subject": target_subject,
                    "target_role": target_role,
                    "action": action,
                    "actor_subject": actor_subject,
                    "actor_type": actor_type,
                    "request_id": request_id,
                },
            )
        ).one()
        await session.commit()
        return {
            "id": row.member_id,
            "subject": row.member_subject,
            "role": row.member_role,
            "status": row.member_status,
        }


async def accept_invitation(
    factory: async_sessionmaker[AsyncSession],
    *,
    tenant_slug: str,
    actor_subject: str,
    request_id: UUID,
) -> dict[str, object]:
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT tenant_id, tenant_slug, member_role
                    FROM public.aegis_accept_tenant_invitation(
                        :tenant_slug, :actor_subject, :request_id
                    )
                    """
                ),
                {
                    "tenant_slug": tenant_slug,
                    "actor_subject": actor_subject,
                    "request_id": request_id,
                },
            )
        ).one()
        await session.commit()
        return {"tenant_id": row.tenant_id, "slug": row.tenant_slug, "role": row.member_role}
