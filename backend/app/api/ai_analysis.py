"""Authenticated, tenant-scoped advisory AI analysis API."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.repositories.audit import PostgresAuditEventSink
from app.security.audit import AuditEvent, AuditOutcome
from app.security.authorization import AuthorizationReason, authorize
from app.security.identity import Permission, Principal
from app.security.tenant import TenantContext, get_tenant_context
from app.security.authentication import get_current_principal

router = APIRouter(prefix="/api/v1/ai", tags=["ai-analysis"])


class AnalysisKind(StrEnum):
    ALERT_TRIAGE = "alert_triage"
    THREAT_INTELLIGENCE = "threat_intelligence"
    VULNERABILITY_ANALYSIS = "vulnerability_analysis"
    INCIDENT_INVESTIGATION = "incident_investigation"


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    source_type: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=12_000)


class AnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AnalysisKind
    evidence: list[EvidenceInput] = Field(min_length=1, max_length=20)
    analyst_context: str = Field(default="", max_length=4_000)


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    kind: AnalysisKind
    analysis: str
    evidence_ids: list[str]
    provider: str
    model: str
    advisory_only: bool = True
    requires_human_review: bool = True


class SpecialistAnalysisService(Protocol):
    """Adapter around the AI specialist runtime; receives server-derived tenant context."""

    async def analyze(
        self,
        *,
        kind: AnalysisKind,
        tenant_id: UUID,
        request_id: UUID,
        evidence: list[EvidenceInput],
        analyst_context: str,
    ) -> AnalysisOutput: ...


def _audit_sink(request: Request) -> PostgresAuditEventSink:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="audit_store_unavailable",
        )
    return PostgresAuditEventSink(factory)


@router.post("/analysis", response_model=AnalysisOutput, status_code=status.HTTP_200_OK)
async def run_advisory_analysis(
    payload: AnalysisInput,
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    principal: Principal = Depends(get_current_principal),
) -> AnalysisOutput:
    """Run one advisory specialist using only the authenticated tenant's supplied evidence."""

    decision = authorize(principal, Permission.INVESTIGATION_CREATE)
    audit = _audit_sink(request)
    request_id = uuid4()

    if not decision.allowed:
        await audit.append(
            AuditEvent(
                tenant_id=tenant.tenant_id,
                actor_subject=principal.subject,
                actor_type=principal.principal_type,
                action="ai.analysis.request",
                resource_type="ai_analysis",
                resource_id=str(request_id),
                outcome=AuditOutcome.DENIED,
                authorization_reason=decision.reason,
                correlation_id=request_id,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ai_analysis_not_permitted",
        )

    service: SpecialistAnalysisService | None = getattr(
        request.app.state, "specialist_analysis_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ai_analysis_service_unavailable",
        )

    if sum(len(item.content) for item in payload.evidence) > 30_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="combined_evidence_too_large",
        )
    evidence_ids = [item.evidence_id for item in payload.evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="evidence_ids_must_be_unique",
        )

    try:
        result = await service.analyze(
            kind=payload.kind,
            tenant_id=tenant.tenant_id,
            request_id=request_id,
            evidence=payload.evidence,
            analyst_context=payload.analyst_context,
        )
    except Exception:
        # Provider failures are sanitized; request payloads and credentials stay out of logs.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ai_provider_unavailable",
        ) from None
    if (
        result.request_id != request_id
        or result.kind != payload.kind
        or set(result.evidence_ids) - set(evidence_ids)
        or not result.advisory_only
        or not result.requires_human_review
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ai_analysis_contract_violation",
        )

    await audit.append(
        AuditEvent(
            tenant_id=tenant.tenant_id,
            actor_subject=principal.subject,
            actor_type=principal.principal_type,
            action="ai.analysis.request",
            resource_type="ai_analysis",
            resource_id=str(request_id),
            outcome=AuditOutcome.SUCCEEDED,
            authorization_reason=AuthorizationReason.GRANTED,
            correlation_id=request_id,
        )
    )
    return result
