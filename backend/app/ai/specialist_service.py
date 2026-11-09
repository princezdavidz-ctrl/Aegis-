"""Adapter from the FastAPI boundary to the shared AEGIS AI specialist runtime."""

from __future__ import annotations

from uuid import UUID

from aegis_ai.specialists import (
    EvidenceItem,
    SpecialistKind,
    SpecialistOrchestrator,
    GenerationRequest,
    GenerationResult,
    GenerationClient,
)

from app.api.ai_analysis import (
    AnalysisKind,
    AnalysisOutput,
    EvidenceInput,
)


class SpecialistAnalysisAdapter:
    """Translate validated API inputs into the provider-neutral specialist runtime."""

    def __init__(self, client: GenerationClient) -> None:
        self._orchestrator = SpecialistOrchestrator(client)

    async def analyze(
        self,
        *,
        kind: AnalysisKind,
        tenant_id: UUID,
        request_id: UUID,
        evidence: list[EvidenceInput],
        analyst_context: str,
    ) -> AnalysisOutput:
        request = SpecialistRequest(
            kind=SpecialistKind(kind.value),
            tenant_id=str(tenant_id),
            request_id=str(request_id),
            evidence=tuple(
                EvidenceItem(
                    evidence_id=item.evidence_id,
                    source_type=item.source_type,
                    content=item.content,
                )
                for item in evidence
            ),
            analyst_context=analyst_context,
        )
        result = await self._orchestrator.analyze(request)
        generation = result.generation
        return AnalysisOutput(
            request_id=request_id,
            kind=kind,
            analysis=generation.text,
            evidence_ids=list(result.evidence_ids),
            provider=generation.provider,
            model=generation.model,
            advisory_only=result.advisory_only,
            requires_human_review=result.requires_human_review,
        )
