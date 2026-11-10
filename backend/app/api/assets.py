"""Tenant-scoped asset inventory APIs."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.db.models import Asset
from app.repositories.assets import create_asset, list_assets, update_asset
from app.security.authentication import get_current_principal
from app.security.identity import Principal
from app.security.tenant import TenantContext, get_tenant_context, get_tenant_session

router=APIRouter(prefix="/api/v1/assets",tags=["asset-inventory"])
ASSET_TYPES={"cloud_account","endpoint","server","domain","repository","network","application","database","user_identity","other"}
ENVIRONMENTS={"production","staging","development","test","unknown"}
CRITICALITIES={"critical","high","medium","low"}

class AssetView(BaseModel):
    model_config=ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    tenant_id: UUID
    name: str
    asset_type: str
    external_id: str | None
    environment: str
    criticality: str
    source: str
    status: str
    created_at: datetime
    updated_at: datetime

class AssetCreateInput(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    name: str=Field(min_length=1,max_length=160)
    asset_type: str
    external_id: str | None=Field(default=None,max_length=160)
    environment: str="unknown"
    criticality: str="medium"
    @field_validator("name","external_id")
    @classmethod
    def normalize_text(cls,v):
        if v is None:return None
        v=v.strip()
        if not v:raise ValueError("value must not be blank")
        return v
    @field_validator("asset_type")
    @classmethod
    def validate_type(cls,v):
        if v not in ASSET_TYPES:raise ValueError("unsupported asset type")
        return v
    @field_validator("environment")
    @classmethod
    def validate_environment(cls,v):
        if v not in ENVIRONMENTS:raise ValueError("unsupported environment")
        return v
    @field_validator("criticality")
    @classmethod
    def validate_criticality(cls,v):
        if v not in CRITICALITIES:raise ValueError("unsupported criticality")
        return v

class AssetUpdateInput(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    name: str | None=Field(default=None,max_length=160)
    asset_type: str | None=None
    external_id: str | None=Field(default=None,max_length=160)
    environment: str | None=None
    criticality: str | None=None
    status: str | None=None
    @field_validator("name","external_id")
    @classmethod
    def normalize_update_text(cls,v):
        if v is None:return None
        v=v.strip()
        if not v:raise ValueError("value must not be blank")
        return v
    @model_validator(mode="after")
    def validate_update(self):
        if not any(v is not None for v in (self.name,self.asset_type,self.external_id,self.environment,self.criticality,self.status)):
            raise ValueError("at least one non-null asset field must be supplied")
        if self.name is not None and not self.name.strip():raise ValueError("name must not be blank")
        if self.asset_type is not None and self.asset_type not in ASSET_TYPES:raise ValueError("unsupported asset type")
        if self.external_id is not None and not self.external_id.strip():raise ValueError("external_id must not be blank")
        if self.environment is not None and self.environment not in ENVIRONMENTS:raise ValueError("unsupported environment")
        if self.criticality is not None and self.criticality not in CRITICALITIES:raise ValueError("unsupported criticality")
        if self.status is not None and self.status not in {"active","archived"}:raise ValueError("unsupported asset status")
        return self

def _provisioner_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory=getattr(request.app.state,"provisioner_session_factory",None)
    if factory is None:raise HTTPException(status_code=503,detail="asset_service_unavailable")
    return factory

def _require_asset_manager(tenant: TenantContext) -> None:
    if tenant.role not in {"tenant_admin","security_manager"}:
        raise HTTPException(status_code=403,detail="asset_manager_required")

def _db_error(exc: DBAPIError) -> HTTPException:
    state=getattr(exc.orig,"sqlstate",None)
    if state=="42501":return HTTPException(status_code=403,detail="asset_manager_required")
    if state=="P0002":return HTTPException(status_code=404,detail="asset_not_found")
    if state=="23505":return HTTPException(status_code=409,detail="asset_external_id_conflict")
    if state=="22023":return HTTPException(status_code=422,detail="invalid_asset")
    return HTTPException(status_code=503,detail="asset_service_unavailable")

@router.get("",response_model=list[AssetView])
async def get_assets(tenant: TenantContext=Depends(get_tenant_context),
    session: AsyncSession=Depends(get_tenant_session),
    include_archived: bool=False,limit: int=Query(default=50,ge=1,le=100),
    offset: int=Query(default=0,ge=0)) -> list[AssetView]:
    assets=await list_assets(session,tenant.tenant_id,include_archived=include_archived,limit=limit,offset=offset)
    return [AssetView.model_validate(a) for a in assets]

@router.post("",response_model=AssetView,status_code=201)
async def add_asset(payload: AssetCreateInput,request: Request,
    tenant: TenantContext=Depends(get_tenant_context),
    principal: Principal=Depends(get_current_principal)) -> AssetView:
    _require_asset_manager(tenant)
    try:
        result=await create_asset(_provisioner_factory(request),tenant_id=tenant.tenant_id,
            actor_subject=principal.subject,actor_type=principal.principal_type.value,request_id=uuid4(),
            name=payload.name,asset_type=payload.asset_type,external_id=payload.external_id,
            environment=payload.environment,criticality=payload.criticality)
    except DBAPIError as exc:raise _db_error(exc) from None
    except SQLAlchemyError:raise HTTPException(status_code=503,detail="asset_service_unavailable") from None
    return AssetView.model_validate(result)

@router.patch("/{asset_id}",response_model=AssetView)
async def change_asset(asset_id: UUID,payload: AssetUpdateInput,request: Request,
    tenant: TenantContext=Depends(get_tenant_context),
    principal: Principal=Depends(get_current_principal)) -> AssetView:
    _require_asset_manager(tenant)
    try:
        result=await update_asset(_provisioner_factory(request),tenant_id=tenant.tenant_id,asset_id=asset_id,
            actor_subject=principal.subject,actor_type=principal.principal_type.value,request_id=uuid4(),
            name=payload.name,asset_type=payload.asset_type,external_id=payload.external_id,
            environment=payload.environment,criticality=payload.criticality,status=payload.status)
    except DBAPIError as exc:raise _db_error(exc) from None
    except SQLAlchemyError:raise HTTPException(status_code=503,detail="asset_service_unavailable") from None
    return AssetView.model_validate(result)
