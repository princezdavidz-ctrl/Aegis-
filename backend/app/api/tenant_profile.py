"""Tenant profile read and administration endpoints."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.models import Tenant
from app.repositories.tenant_profile import update_tenant_profile
from app.security.authentication import get_current_principal
from app.security.identity import Principal
from app.security.tenant import TenantContext, get_tenant_context, get_tenant_session

router = APIRouter(prefix="/api/v1/tenants/profile", tags=["tenant-profile"])

class TenantProfileView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    slug: str
    display_name: str
    industry: str | None
    organization_size: str | None
    region: str | None
    data_retention_days: int
    policy_profile: str
    created_at: datetime

class TenantProfileUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    industry: str | None = Field(default=None, max_length=80)
    organization_size: str | None = None
    region: str | None = Field(default=None, max_length=64)
    data_retention_days: int | None = Field(default=None, ge=30, le=3650)
    policy_profile: str | None = None

    @field_validator("industry","region")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None: return None
        value = value.strip()
        if not value: raise ValueError("value must not be blank")
        return value

    @field_validator("organization_size")
    @classmethod
    def validate_size(cls, value: str | None) -> str | None:
        if value is not None and value not in {"1-10","11-50","51-200","201-1000","1000+"}:
            raise ValueError("unsupported organization size")
        return value

    @field_validator("policy_profile")
    @classmethod
    def validate_policy(cls, value: str | None) -> str | None:
        if value is not None and value not in {"baseline","strict","regulated"}:
            raise ValueError("unsupported policy profile")
        return value

    @model_validator(mode="after")
    def require_update(self) -> TenantProfileUpdateInput:
        if not any(v is not None for v in (self.industry,self.organization_size,self.region,self.data_retention_days,self.policy_profile)):
            raise ValueError("at least one non-null profile field must be supplied")
        return self

def _provisioner_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state,"provisioner_session_factory",None)
    if factory is None: raise HTTPException(status_code=503,detail="tenant_profile_service_unavailable")
    return factory

def _require_admin(tenant: TenantContext) -> None:
    if tenant.role != "tenant_admin": raise HTTPException(status_code=403,detail="tenant_admin_required")

def _translate_error(exc: DBAPIError) -> HTTPException:
    state = getattr(exc.orig,"sqlstate",None)
    if state == "42501": return HTTPException(status_code=403,detail="tenant_admin_required")
    if state == "P0002": return HTTPException(status_code=404,detail="tenant_not_found")
    if state == "22023": return HTTPException(status_code=422,detail="invalid_tenant_profile")
    return HTTPException(status_code=503,detail="tenant_profile_service_unavailable")

@router.get("",response_model=TenantProfileView)
async def read_tenant_profile(tenant: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session)) -> TenantProfileView:
    profile = await session.get(Tenant,tenant.tenant_id)
    if profile is None: raise HTTPException(status_code=404,detail="tenant_not_found")
    return TenantProfileView.model_validate({
        "id":profile.id,"slug":profile.slug,"display_name":profile.display_name,
        "industry":profile.industry,"organization_size":profile.organization_size,
        "region":profile.region,"data_retention_days":profile.data_retention_days,
        "policy_profile":profile.policy_profile,"created_at":profile.created_at,
    })

@router.patch("",response_model=TenantProfileView)
async def update_profile(payload: TenantProfileUpdateInput, request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal)) -> TenantProfileView:
    _require_admin(tenant)
    try:
        updated = await update_tenant_profile(
            _provisioner_factory(request),tenant_id=tenant.tenant_id,
            actor_subject=principal.subject,actor_type=principal.principal_type.value,
            request_id=uuid4(),industry=payload.industry,
            organization_size=payload.organization_size,region=payload.region,
            data_retention_days=payload.data_retention_days,policy_profile=payload.policy_profile,
        )
    except DBAPIError as exc:
        raise _translate_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503,detail="tenant_profile_service_unavailable") from None
    return TenantProfileView.model_validate(updated)
