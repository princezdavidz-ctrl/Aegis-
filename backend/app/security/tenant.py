"""Request tenant context resolved from verified identity and membership."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.tenants import resolve_active_membership
from app.security.authentication import get_current_principal
from app.security.identity import Principal


class TenantContext(BaseModel):
    """Immutable tenant authority derived from a persisted membership."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: UUID
    membership_id: UUID
    tenant_slug: str = Field(min_length=1, max_length=63)
    role: str = Field(min_length=1, max_length=48)
    subject: str = Field(min_length=1, max_length=128)


async def get_tenant_context(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    tenant_slug: str = Header(alias="X-AEGIS-Tenant", min_length=1, max_length=63),
) -> TenantContext:
    """Resolve selected tenant through server-side membership; fail closed."""

    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tenant_membership_store_unavailable",
        )

    async with factory() as session:
        membership = await resolve_active_membership(
            session, subject=principal.subject, tenant_slug=tenant_slug
        )

    if membership is None:
        # Do not reveal whether the tenant exists or membership is inactive.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_access_denied",
        )

    tenant_id, membership_id, resolved_slug, role = membership
    return TenantContext(
        tenant_id=tenant_id,
        membership_id=membership_id,
        tenant_slug=resolved_slug,
        role=role,
        subject=principal.subject,
    )
