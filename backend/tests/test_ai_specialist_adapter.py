"""Tests for the FastAPI-to-specialist-runtime adapter."""

from uuid import UUID, uuid4

import pytest

from aegis_ai.contracts import GenerationRequest, GenerationResult

from app.ai.specialist_service import SpecialistAnalysisAdapter
from app.api.ai_analysis import AnalysisKind, EvidenceInput


class FakeModelGateway:
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        assert request.tenant_id == TENANT_ID
        assert request.request_id == REQUEST_ID
        assert "untrusted data" in request.system_instruction
        return GenerationResult(
            text="Suspicious login requires analyst validation. Evidence: evt-1",
            provider="test-provider",
            model="test-model",
            finish_reason="stop",
        )


TENANT_ID = str(uuid4())
REQUEST_ID = str(uuid4())


@pytest.mark.asyncio
async def test_adapter_dispatches_tenant_scoped_alert_triage() -> None:
    adapter = SpecialistAnalysisAdapter(FakeModelGateway())
    result = await adapter.analyze(
        kind=AnalysisKind.ALERT_TRIAGE,
        tenant_id=UUID(TENANT_ID),
        request_id=UUID(REQUEST_ID),
        evidence=[
            EvidenceInput(
                evidence_id="evt-1",
                source_type="authentication_alert",
                content="Repeated failed logins followed by a successful login.",
            )
        ],
        analyst_context="Assess whether this merits escalation.",
    )

    assert result.request_id == UUID(REQUEST_ID)
    assert result.kind == AnalysisKind.ALERT_TRIAGE
    assert result.evidence_ids == ["evt-1"]
    assert result.provider == "test-provider"
    assert result.model == "test-model"
    assert result.advisory_only is True
    assert result.requires_human_review is True
