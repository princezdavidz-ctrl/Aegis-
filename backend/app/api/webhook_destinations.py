"""Tenant-manager API for KMS-encrypted outbound webhook destinations."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import secrets
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.endpoint.webhook_secrets import KMSWebhookSecretProvider
from app.endpoint.webhooks import WebhookConfigurationError, validate_webhook_url
from app.repositories.webhook_destinations import (
    create_webhook_destination,
    disable_webhook_destination,
    list_webhook_destinations,
)
from app.security.authentication import get_current_principal
from app.security.identity import Principal
from app.security.tenant import TenantContext, get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhook-destinations", tags=["webhook-destinations"])
_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class WebhookDestinationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=120)
    target_url: str = Field(min_length=9, max_length=2048)
    event_types: list[str] = Field(min_length=1, max_length=32)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("name must be non-empty and contain no control characters")
        return value

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, value: str) -> str:
        try:
            return validate_webhook_url(value)
        except WebhookConfigurationError as exc:
            raise ValueError("target_url must be a public HTTPS URL") from exc

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or any(not _EVENT_TYPE.fullmatch(v) for v in values):
            raise ValueError("event_types must be unique lowercase event identifiers")
        return values


class WebhookDestinationView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: str
    target_url: str
    status: str
    event_types: list[str]
    secret_version: int
    created_at: datetime
    updated_at: datetime | None = None
    disabled_at: datetime | None = None


class WebhookDestinationCreated(WebhookDestinationView):
    # Returned exactly once. It is never persisted or included in list responses.
    signing_secret: str


def _provisioner_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "provisioner_session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="webhook_destination_service_unavailable")
    return factory


def _secret_provider(request: Request) -> KMSWebhookSecretProvider:
    provider = getattr(request.app.state, "webhook_secret_provider", None)
    if provider is None:
        raise HTTPException(status_code=503, detail="webhook_kms_not_configured")
    return provider


def _require_manager(tenant: TenantContext) -> None:
    if tenant.role not in {"tenant_admin", "security_manager"}:
        raise HTTPException(status_code=403, detail="webhook_manager_required")


def _database_error(exc: DBAPIError) -> HTTPException:
    state = getattr(exc.orig, "sqlstate", None)
    if state == "42501":
        return HTTPException(status_code=403, detail="webhook_manager_required")
    if state == "P0002":
        return HTTPException(status_code=404, detail="webhook_destination_not_found")
    if state == "22023":
        return HTTPException(status_code=422, detail="invalid_webhook_destination")
    if state == "23505":
        return HTTPException(status_code=409, detail="webhook_destination_conflict")
    return HTTPException(status_code=503, detail="webhook_destination_service_unavailable")


@router.post("", response_model=WebhookDestinationCreated, status_code=status.HTTP_201_CREATED)
async def create_destination(
    payload: WebhookDestinationCreate,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal),
) -> WebhookDestinationCreated:
    """Create a destination and reveal its random signing secret once."""
    _require_manager(tenant)
    destination_id = uuid4()
    signing_secret = secrets.token_bytes(32)
    provider = _secret_provider(request)
    try:
        envelope = await asyncio.to_thread(
            provider.encrypt,
            signing_secret,
            tenant_id=str(tenant.tenant_id),
            destination_id=str(destination_id),
            secret_version=1,
        )
        result = await create_webhook_destination(
            _provisioner_factory(request),
            tenant_id=tenant.tenant_id,
            destination_id=destination_id,
            actor=principal.subject,
            name=payload.name,
            target_url=payload.target_url,
            event_types=payload.event_types,
            secret_ciphertext=envelope,
            secret_key_ref=provider.key_id,
            secret_encryption_version=1,
            secret_version=1,
        )
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="webhook_destination_service_unavailable") from None
    except Exception:
        logger.warning("Webhook destination encryption or persistence failed")
        raise HTTPException(status_code=503, detail="webhook_destination_service_unavailable") from None

    return WebhookDestinationCreated(
        **result,
        signing_secret=base64.urlsafe_b64encode(signing_secret).decode("ascii").rstrip("="),
    )


@router.get("", response_model=list[WebhookDestinationView])
async def get_destinations(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal),
) -> list[WebhookDestinationView]:
    _require_manager(tenant)
    try:
        rows = await list_webhook_destinations(
            _provisioner_factory(request), tenant_id=tenant.tenant_id, actor=principal.subject
        )
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="webhook_destination_service_unavailable") from None
    return [WebhookDestinationView(**row) for row in rows]


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_destination(
    destination_id: UUID,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    _require_manager(tenant)
    try:
        await disable_webhook_destination(
            _provisioner_factory(request),
            tenant_id=tenant.tenant_id,
            destination_id=destination_id,
            actor=principal.subject,
        )
    except DBAPIError as exc:
        raise _database_error(exc) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="webhook_destination_service_unavailable") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
