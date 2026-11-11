"""Authenticated endpoint enrollment, signed ingestion and revocation APIs."""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.endpoint.identity import create_enrollment_token, verify_endpoint_event_signature
from app.endpoint.schemas import EndpointPlatform, EndpointTelemetryEnvelope
from app.repositories.endpoint_devices import (
    accept_event, create_invitation, get_active_device_key, redeem_invitation, revoke_device,
)
from app.security.authentication import get_current_principal
from app.security.identity import Principal
from app.security.tenant import TenantContext, get_tenant_context

router = APIRouter(prefix="/api/v1/endpoints", tags=["endpoint-security"])


class InvitationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    platform: EndpointPlatform
    ttl_minutes: int = Field(default=60, ge=5, le=1440)


class InvitationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    invitation_id: UUID
    platform: EndpointPlatform
    expires_at: datetime
    enrollment_token: str


class EnrollmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enrollment_token: str = Field(min_length=32, max_length=256)
    platform: EndpointPlatform
    public_key_b64: str = Field(min_length=40, max_length=64)
    hostname: str = Field(min_length=1, max_length=255)
    agent_version: str = Field(min_length=1, max_length=64)

    @field_validator("hostname", "agent_version")
    @classmethod
    def normalize_metadata(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("metadata must be non-empty and contain no control characters")
        return value


class EnrollmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    device_id: UUID
    platform: EndpointPlatform
    hostname: str
    agent_version: str
    enrolled_at: datetime


class SignedEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event: EndpointTelemetryEnvelope
    signature_b64: str = Field(min_length=80, max_length=100)


class EventAcceptedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    device_id: UUID
    event_id: UUID
    sequence: int
    received_at: datetime


def _provisioner_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "provisioner_session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="endpoint_service_unavailable")
    return factory


def _require_endpoint_manager(tenant: TenantContext) -> None:
    if tenant.role not in {"tenant_admin", "security_manager"}:
        raise HTTPException(status_code=403, detail="endpoint_manager_required")


def _database_error(exc: DBAPIError) -> HTTPException:
    state = getattr(exc.orig, "sqlstate", None)
    if state == "42501":
        return HTTPException(status_code=403, detail="endpoint_manager_required")
    if state == "P0002":
        return HTTPException(status_code=404, detail="endpoint_not_found_or_invalid_invitation")
    if state == "23505":
        return HTTPException(status_code=409, detail="endpoint_event_replay_or_conflict")
    if state == "22023":
        return HTTPException(status_code=422, detail="invalid_endpoint_request")
    return HTTPException(status_code=503, detail="endpoint_service_unavailable")


@router.post("/invitations", response_model=InvitationOutput, status_code=status.HTTP_201_CREATED)
async def issue_invitation(payload: InvitationInput, request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal)) -> InvitationOutput:
    _require_endpoint_manager(tenant)
    token, digest = create_enrollment_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=payload.ttl_minutes)
    try:
        result = await create_invitation(_provisioner_factory(request), tenant_id=tenant.tenant_id,
            actor=principal.subject, actor_type=principal.principal_type.value,
            request_id=uuid4(), digest=digest, platform=payload.platform.value, expires_at=expires_at)
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="endpoint_service_unavailable") from None
    return InvitationOutput(invitation_id=result["id"], platform=result["platform"],
        expires_at=result["expires_at"], enrollment_token=token)


@router.post("/enroll", response_model=EnrollmentOutput, status_code=status.HTTP_201_CREATED)
async def enroll_device(payload: EnrollmentInput, request: Request) -> EnrollmentOutput:
    try:
        public_key = base64.b64decode(payload.public_key_b64, validate=True)
        if len(public_key) != 32:
            raise ValueError("invalid Ed25519 public key")
        fingerprint = hashlib.sha256(public_key).hexdigest()
        result = await redeem_invitation(_provisioner_factory(request),
            digest=hashlib.sha256(payload.enrollment_token.encode("utf-8")).hexdigest(),
            platform=payload.platform.value, public_key_b64=payload.public_key_b64,
            fingerprint=fingerprint, hostname=payload.hostname, agent_version=payload.agent_version)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="invalid_endpoint_enrollment") from None
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="endpoint_service_unavailable") from None
    return EnrollmentOutput(device_id=result["id"], platform=result["platform"],
        hostname=result["hostname"], agent_version=result["agent_version"],
        enrolled_at=datetime.now(timezone.utc))


@router.post("/events", response_model=EventAcceptedOutput, status_code=status.HTTP_202_ACCEPTED)
async def ingest_signed_event(payload: SignedEventInput, request: Request) -> EventAcceptedOutput:
    factory = _provisioner_factory(request)
    event = payload.event
    try:
        identity = await get_active_device_key(factory, device_id=event.device_id)
        if identity is None or not verify_endpoint_event_signature(event,
            public_key_b64=identity["public_key_b64"], signature_b64=payload.signature_b64):
            raise HTTPException(status_code=401, detail="invalid_endpoint_credential")
        result = await accept_event(factory, device_id=event.device_id, sequence=event.sequence,
            event_id=event.event_id, event_type=event.event_type.value,
            observed_at=event.observed_at, payload=event.payload)
    except HTTPException:
        raise
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="endpoint_service_unavailable") from None
    return EventAcceptedOutput(device_id=result["device_id"], event_id=result["event_id"],
        sequence=result["sequence"], received_at=result["received_at"])


@router.post("/{device_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_endpoint(device_id: UUID, request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal)) -> None:
    _require_endpoint_manager(tenant)
    try:
        await revoke_device(_provisioner_factory(request), tenant_id=tenant.tenant_id,
            device_id=device_id, actor=principal.subject,
            actor_type=principal.principal_type.value, request_id=uuid4())
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="endpoint_service_unavailable") from None
