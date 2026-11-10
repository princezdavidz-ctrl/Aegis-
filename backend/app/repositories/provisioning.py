"""Database function adapter for tightly scoped tenant provisioning."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def provision_tenant(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    slug: str,
    display_name: str,
    initial_admin_subject: str,
    actor_subject: str,
    actor_type: str,
    request_id: UUID,
) -> tuple[UUID, str]:
    """Call the SECURITY DEFINER function using the isolated provisioner role."""

    async with session_factory() as session:
        result = await session.execute(
            text(
                """
                SELECT tenant_id, tenant_slug
                FROM public.aegis_provision_tenant(
                    :slug,
                    :display_name,
                    :initial_admin_subject,
                    :actor_subject,
                    :actor_type,
                    :request_id
                )
                """
            ),
            {
                "slug": slug,
                "display_name": display_name,
                "initial_admin_subject": initial_admin_subject,
                "actor_subject": actor_subject,
                "actor_type": actor_type,
                "request_id": request_id,
            },
        )
        row = result.one()
        await session.commit()
        return row[0], row[1]
