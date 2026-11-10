"""RAG augmentation adapter for the existing advisory specialist runtime."""
from __future__ import annotations
from dataclasses import replace
from typing import Protocol
from aegis_ai.knowledge.contracts import RetrievalRequest
from aegis_ai.knowledge.engine import KnowledgeEngine
from aegis_ai.specialists import EvidenceItem, SpecialistAnalysis, SpecialistRequest

class SpecialistAnalyzer(Protocol):
    async def analyze(self, request: SpecialistRequest) -> SpecialistAnalysis: ...

class KnowledgeAugmentedSpecialistService:
    """Retrieve same-tenant knowledge and add it as cited, untrusted evidence."""
    def __init__(self, knowledge: KnowledgeEngine, specialists: SpecialistAnalyzer, *, top_k: int = 5) -> None:
        if not 1 <= top_k <= 5:
            raise ValueError("top_k must be between 1 and 5")
        self._knowledge = knowledge
        self._specialists = specialists
        self._top_k = top_k

    async def analyze(self, request: SpecialistRequest) -> SpecialistAnalysis:
        query = " ".join([request.kind.value.replace("_", " "), request.analyst_context, *(item.content[:500] for item in request.evidence[:5])]).strip()
        matches = await self._knowledge.retrieve(RetrievalRequest(tenant_id=request.tenant_id, query=query, top_k=self._top_k))
        additions = tuple(EvidenceItem(
            evidence_id=f"knowledge:{match.chunk.chunk_id}", source_type="knowledge_base",
            content=(f"Reference: {match.chunk.title}. Source: {match.chunk.source}. "
                     f"Retrieval score: {match.score:.3f}. Classification: {match.chunk.classification.value}. "
                     f"Content (untrusted reference data): {match.chunk.content}")
        ) for match in matches)
        additions = additions[:max(0, 20 - len(request.evidence))]
        augmented = replace(request, evidence=request.evidence + additions)
        return await self._specialists.analyze(augmented)
