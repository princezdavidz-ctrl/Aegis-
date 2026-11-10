"""Tenant-scoped integration request, approval and revocation APIs."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from sqlalchemy.exc import DBAPIError,SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker
from app.db.models import Integration
from app.repositories.integrations import approve_integration,list_integrations,request_integration,revoke_integration
from app.security.authentication import get_current_principal
from app.security.identity import Principal
from app.security.tenant import TenantContext,get_tenant_context,get_tenant_session

router=APIRouter(prefix="/api/v1/integrations",tags=["integrations"])
PROVIDER_SCOPES={
 "github":{"repositories:read","alerts:read","security-events:read"},
 "aws":{"cloud-inventory:read","security-findings:read","config:read","logs:read"},
 "azure":{"cloud-inventory:read","security-findings:read","logs:read"},
 "gcp":{"cloud-inventory:read","security-findings:read","logs:read"},
 "wazuh":{"alerts:read","endpoint-inventory:read"},
 "suricata":{"network-events:read"},
 "trivy":{"vulnerabilities:read"},
 "semgrep":{"code-findings:read"},
}

class IntegrationView(BaseModel):
 model_config=ConfigDict(extra="forbid",from_attributes=True)
 id: UUID
 tenant_id: UUID
 provider: str
 display_name: str
 external_account_id: str | None
 status: str
 access_mode: str
 requested_scopes: list[str]
 approved_scopes: list[str]
 created_by: str
 approved_by: str | None
 approved_at: datetime | None
 created_at: datetime
 updated_at: datetime

class IntegrationRequestInput(BaseModel):
 model_config=ConfigDict(extra="forbid",frozen=True)
 provider: str
 display_name: str=Field(min_length=1,max_length=120)
 external_account_id: str | None=Field(default=None,max_length=160)
 requested_scopes: list[str]=Field(min_length=1,max_length=10)
 @field_validator("provider")
 @classmethod
 def validate_provider(cls,v):
  if v not in PROVIDER_SCOPES:raise ValueError("unsupported integration provider")
  return v
 @field_validator("display_name","external_account_id")
 @classmethod
 def normalize_text(cls,v):
  if v is None:return None
  v=v.strip()
  if not v:raise ValueError("value must not be blank")
  return v
 @model_validator(mode="after")
 def validate_scopes(self):
  if len(set(self.requested_scopes))!=len(self.requested_scopes):raise ValueError("duplicate scopes are not allowed")
  if any(scope not in PROVIDER_SCOPES[self.provider] for scope in self.requested_scopes):
   raise ValueError("requested scopes exceed the provider read-only allowlist")
  return self

class IntegrationApprovalInput(BaseModel):
 model_config=ConfigDict(extra="forbid",frozen=True)
 approved_scopes: list[str]=Field(min_length=1,max_length=10)
 @field_validator("approved_scopes")
 @classmethod
 def validate_scopes(cls,v):
  if len(set(v))!=len(v):raise ValueError("duplicate scopes are not allowed")
  if any(not scope.endswith(":read") or scope=="*" for scope in v):raise ValueError("only explicit read-only scopes may be approved")
  return v

def _factory(request: Request) -> async_sessionmaker[AsyncSession]:
 factory=getattr(request.app.state,"provisioner_session_factory",None)
 if factory is None:raise HTTPException(status_code=503,detail="integration_service_unavailable")
 return factory

def _require_manager(tenant: TenantContext) -> None:
 if tenant.role not in {"tenant_admin","security_manager"}:raise HTTPException(status_code=403,detail="integration_manager_required")

def _require_admin(tenant: TenantContext) -> None:
 if tenant.role!="tenant_admin":raise HTTPException(status_code=403,detail="tenant_admin_required")

def _db_error(exc: DBAPIError) -> HTTPException:
 state=getattr(exc.orig,"sqlstate",None)
 if state=="42501":return HTTPException(status_code=403,detail="integration_permission_denied")
 if state=="P0002":return HTTPException(status_code=404,detail="integration_not_found")
 if state=="23505":return HTTPException(status_code=409,detail="integration_already_exists")
 if state=="23514":return HTTPException(status_code=409,detail="integration_state_conflict")
 if state=="22023":return HTTPException(status_code=422,detail="invalid_integration_request")
 return HTTPException(status_code=503,detail="integration_service_unavailable")

@router.get("",response_model=list[IntegrationView])
async def get_integrations(tenant: TenantContext=Depends(get_tenant_context),
 session: AsyncSession=Depends(get_tenant_session)) -> list[IntegrationView]:
 rows=await list_integrations(session,tenant.tenant_id)
 return [IntegrationView.model_validate(row) for row in rows]

@router.post("",response_model=IntegrationView,status_code=201)
async def create_integration_request(payload: IntegrationRequestInput,request: Request,
 tenant: TenantContext=Depends(get_tenant_context),
 principal: Principal=Depends(get_current_principal)) -> IntegrationView:
 _require_manager(tenant)
 try:
  result=await request_integration(_factory(request),tenant_id=tenant.tenant_id,
   actor_subject=principal.subject,actor_type=principal.principal_type.value,request_id=uuid4(),
   provider=payload.provider,display_name=payload.display_name,
   external_account_id=payload.external_account_id,requested_scopes=payload.requested_scopes)
 except DBAPIError as exc:raise _db_error(exc) from None
 except SQLAlchemyError:raise HTTPException(status_code=503,detail="integration_service_unavailable") from None
 return IntegrationView.model_validate(result)

@router.post("/{integration_id}/approve",response_model=IntegrationView)
async def approve_request(integration_id: UUID,payload: IntegrationApprovalInput,request: Request,
 tenant: TenantContext=Depends(get_tenant_context),
 principal: Principal=Depends(get_current_principal)) -> IntegrationView:
 _require_admin(tenant)
 try:
  result=await approve_integration(_factory(request),tenant_id=tenant.tenant_id,
   integration_id=integration_id,actor_subject=principal.subject,request_id=uuid4(),
   approved_scopes=payload.approved_scopes)
 except DBAPIError as exc:raise _db_error(exc) from None
 except SQLAlchemyError:raise HTTPException(status_code=503,detail="integration_service_unavailable") from None
 return IntegrationView.model_validate(result)

@router.post("/{integration_id}/revoke",response_model=IntegrationView)
async def revoke_request(integration_id: UUID,request: Request,
 tenant: TenantContext=Depends(get_tenant_context),
 principal: Principal=Depends(get_current_principal)) -> IntegrationView:
 _require_admin(tenant)
 try:
  result=await revoke_integration(_factory(request),tenant_id=tenant.tenant_id,
   integration_id=integration_id,actor_subject=principal.subject,request_id=uuid4())
 except DBAPIError as exc:raise _db_error(exc) from None
 except SQLAlchemyError:raise HTTPException(status_code=503,detail="integration_service_unavailable") from None
 return IntegrationView.model_validate(result)
