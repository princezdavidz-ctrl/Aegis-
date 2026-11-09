"""Tenant membership lookup; tenant identifiers come from persisted membership."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MembershipStatus, Tenant, TenantMembership


async def resolve_active_membership(
    session: AsyncSession,
    *,
    subject: str,
    tenant_slug: str,
) -> tuple[UUID, UUID, str, str] | None:
    """Resolve a tenant only when the verified subject has active membership.

    The caller-provided slug is only a selector. The tenant UUID and role are
    returned from the trusted database membership row, never from the request.
    """

    statement = (
        select(Tenant.id, TenantMembership.id, Tenant.slug, TenantMembership.role)
        .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
        .where(
            TenantMembership.subject == subject,
            TenantMembership.status == MembershipStatus.ACTIVE.value,
            Tenant.slug == tenant_slug,
        )
        .limit(1)
    )
    result = await session.execute(statement)
    row = result.one_or_none()
    if row is None:
        return None
    return row[0], row[1], row[2], row[3]
