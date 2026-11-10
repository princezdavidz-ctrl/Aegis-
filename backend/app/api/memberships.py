"""Tenant-scoped customer membership administration and invitation acceptance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.memberships import accept_invitation, list_members, manage_member
from app.security.authentication import get_current_principal
from app.security.identity import Principal
from app.security.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/tenants", tags=["tenant-memberships"])


class MemberInviteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, max_length=128)
    role: str

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 or ord(character) == 127 for character in normalized):
            raise ValueError("subject must be a non-empty opaque identity subject")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"security_manager", "analyst", "viewer"}:
            raise ValueError("role must be security_manager, analyst or viewer")
        return value


class MemberActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: str
    role: str | None = None

    @model_validator(mode="after")
    def validate_action_and_role(self) -> MemberActionInput:
        if self.action not in {"change_role", "suspend", "revoke"}:
            raise ValueError("unsupported membership action")
        if self.action == "change_role" and self.role not in {
            "security_manager", "analyst", "viewer"
        }:
            raise ValueError("a supported role is required for change_role")
        if self.action != "change_role" and self.role is not None:
            raise ValueError("role is only accepted for change_role")
        return self


class MemberView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    subject: str
    role: str
    status: str
    created_at: datetime
    invitation_expires_at: datetime | None = None


class MemberActionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    subject: str
    role: str
    status: str


class InvitationAcceptInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_slug: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$",
    )


class InvitationAcceptView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    slug: str
    role: str
    request_id: UUID


def _provisioner_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "provisioner_session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="membership_service_unavailable",
        )
    return factory


def _require_tenant_admin(tenant: TenantContext) -> None:
    if tenant.role != "tenant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_admin_required",
        )


def _database_error(exc: DBAPIError) -> HTTPException:
    """Translate known database function outcomes without exposing SQL details."""

    sqlstate = getattr(exc.orig, "sqlstate", None)
    if sqlstate == "42501":
        return HTTPException(status_code=403, detail="tenant_admin_required")
    if sqlstate == "P0002":
        return HTTPException(status_code=404, detail="membership_not_found")
    if sqlstate in {"23505", "23514"}:
        return HTTPException(status_code=409, detail="membership_conflict")
    if sqlstate == "22023":
        return HTTPException(status_code=422, detail="invalid_membership_operation")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="membership_service_unavailable",
    )


@router.get("/members", response_model=list[MemberView])
async def get_members(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
) -> list[MemberView]:
    _require_tenant_admin(tenant)
    try:
        members = await list_members(
            _provisioner_factory(request),
            tenant_id=tenant.tenant_id,
            actor_subject=tenant.subject,
        )
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="membership_service_unavailable") from None
    return [MemberView.model_validate(member) for member in members]


@router.post(
    "/members/invitations",
    response_model=MemberActionView,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    payload: MemberInviteInput,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal),
) -> MemberActionView:
    _require_tenant_admin(tenant)
    if payload.subject == principal.subject:
        raise HTTPException(status_code=409, detail="cannot_invite_self")
    try:
        member = await manage_member(
            _provisioner_factory(request),
            tenant_id=tenant.tenant_id,
            target_subject=payload.subject,
            target_role=payload.role,
            action="invite",
            actor_subject=principal.subject,
            actor_type=principal.principal_type.value,
            request_id=uuid4(),
        )
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="membership_service_unavailable") from None
    return MemberActionView.model_validate(member)


@router.patch("/members/{subject:path}", response_model=MemberActionView)
async def update_member(
    subject: str,
    payload: MemberActionInput,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal),
) -> MemberActionView:
    _require_tenant_admin(tenant)
    if subject == principal.subject:
        raise HTTPException(status_code=409, detail="cannot_change_own_membership")
    try:
        member = await manage_member(
            _provisioner_factory(request),
            tenant_id=tenant.tenant_id,
            target_subject=subject,
            target_role=payload.role,
            action=payload.action,
            actor_subject=principal.subject,
            actor_type=principal.principal_type.value,
            request_id=uuid4(),
        )
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="membership_service_unavailable") from None
    return MemberActionView.model_validate(member)


@router.post("/invitations/accept", response_model=InvitationAcceptView)
async def accept_member_invitation(
    payload: InvitationAcceptInput,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> InvitationAcceptView:
    request_id = uuid4()
    try:
        accepted = await accept_invitation(
            _provisioner_factory(request),
            tenant_slug=payload.tenant_slug,
            actor_subject=principal.subject,
            request_id=request_id,
        )
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == "P0002":
            raise HTTPException(status_code=404, detail="invitation_not_found") from None
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="membership_service_unavailable") from None
    return InvitationAcceptView(
        tenant_id=accepted["tenant_id"],
        slug=accepted["slug"],
        role=accepted["role"],
        request_id=request_id,
    )
