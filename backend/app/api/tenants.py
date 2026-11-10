"""Platform-level tenant provisioning endpoint."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.provisioning import provision_tenant
from app.security.authorization import authorize
from app.security.authentication import get_current_principal
from app.security.identity import Permission, Principal

router = APIRouter(prefix="/api/v1/tenants", tags=["tenant-provisioning"])


class TenantProvisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str = Field(min_length=3, max_length=63, pattern=r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
    display_name: str = Field(min_length=1, max_length=160)
    initial_admin_subject: str = Field(min_length=1, max_length=128)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized

    @field_validator("initial_admin_subject")
    @classmethod
    def normalize_initial_admin_subject(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 or ord(character) == 127 for character in normalized):
            raise ValueError("initial_admin_subject must be a non-empty opaque identifier")
        return normalized


class TenantProvisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    slug: str
    display_name: str
    request_id: UUID


def _provisioner_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "provisioner_session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tenant_provisioner_unavailable",
        )
    return factory


@router.post("", response_model=TenantProvisionOutput, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantProvisionInput,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> TenantProvisionOutput:
    """Provision a tenant only for a verified platform principal with exact scope."""

    decision = authorize(principal, Permission.TENANT_PROVISION)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_provision_not_permitted",
        )

    factory = _provisioner_factory(request)
    request_id = uuid4()
    try:
        tenant_id, tenant_slug = await provision_tenant(
            factory,
            slug=payload.slug,
            display_name=payload.display_name,
            initial_admin_subject=payload.initial_admin_subject,
            actor_subject=principal.subject,
            actor_type=principal.principal_type.value,
            request_id=request_id,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tenant_slug_already_exists",
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tenant_provisioning_failed",
        ) from None

    return TenantProvisionOutput(
        tenant_id=tenant_id,
        slug=tenant_slug,
        display_name=payload.display_name,
        request_id=request_id,
    )
