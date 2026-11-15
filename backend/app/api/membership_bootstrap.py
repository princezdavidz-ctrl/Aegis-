"""Self-service bootstrap of active tenant memberships for a verified subject."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import apply_database_context
from app.repositories.tenants import list_active_memberships
from app.security.authentication import get_current_principal
from app.security.identity import Principal

router = APIRouter(prefix="/api/v1/me", tags=["membership-bootstrap"])

TenantRole = Literal["tenant_admin", "security_manager", "analyst", "viewer"]


class ActiveTenantMembershipView(BaseModel):
    """Minimum membership data required by the portal to select a tenant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_slug: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$",
    )
    display_name: str = Field(min_length=1, max_length=160)
    role: TenantRole

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 or ord(character) == 127 for character in normalized):
            raise ValueError("display_name must be a non-empty printable value")
        return normalized


class MembershipBootstrapResponse(BaseModel):
    """A bounded list of active memberships for the authenticated subject."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memberships: list[ActiveTenantMembershipView] = Field(max_length=100)


def _session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tenant_membership_store_unavailable",
        )
    return factory


@router.get("/tenants", response_model=MembershipBootstrapResponse)
async def get_my_tenant_memberships(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> MembershipBootstrapResponse:
    """Return only active memberships for the subject verified from the bearer token.

    No subject, tenant UUID, or role is accepted from the request. The database
    query runs with the verified subject in transaction-local RLS context.
    """

    try:
        async with _session_factory(request)() as session:
            await apply_database_context(session, subject=principal.subject)
            memberships = await list_active_memberships(
                session,
                subject=principal.subject,
            )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tenant_membership_store_unavailable",
        ) from None

    return MembershipBootstrapResponse(
        memberships=[
            ActiveTenantMembershipView(
                tenant_slug=slug,
                display_name=display_name,
                role=role,
            )
            for slug, display_name, role in memberships
        ]
    )
