from __future__ import annotations

import asyncio

import pytest

from aegis_ai.knowledge import (
    InMemoryKnowledgeStore, KnowledgeClassification, KnowledgeDocument,
    KnowledgeEngine, RetrievalRequest,
)
from aegis_ai.knowledge.augmentation import KnowledgeAugmentedSpecialistService
from aegis_ai.knowledge.chunking import chunk_document
from aegis_ai.contracts import GenerationResult
from aegis_ai.specialists import EvidenceItem, SpecialistAnalysis, SpecialistKind, SpecialistRequest


def document(tenant_id: str = "tenant-a", document_id: str = "cve-2026-1234", content: str = (
    "CVE-2026-1234 affects exposed Linux servers running the vulnerable service. "
    "Restrict network exposure, apply the vendor security update, and verify the "
    "installed package version. Check authentication logs for suspicious activity."
)) -> KnowledgeDocument:
    return KnowledgeDocument(
        tenant_id=tenant_id, document_id=document_id,
        title="Linux service vulnerability advisory", source="security-advisory",
        content=content, source_uri="https://security.example/advisories/cve-2026-1234",
        classification=KnowledgeClassification.PUBLIC, updated_at="2026-11-10T00:00:00Z",
    )


def test_chunking_is_stable_and_respects_size() -> None:
    long_document = document(content=("Vulnerability advisory and remediation. " * 90))
    first = chunk_document(long_document, chunk_size=400, overlap=50)
    second = chunk_document(long_document, chunk_size=400, overlap=50)
    assert len(first) > 1
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]
    assert all(len(item.content) <= 400 for item in first)
    assert all(item.tenant_id == "tenant-a" for item in first)


def test_document_rejects_non_https_source() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        KnowledgeDocument("tenant-a", "doc-1", "Unsafe", "manual", "Security content", "http://example.com")


def test_document_rejects_embedded_url_credentials() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        KnowledgeDocument("tenant-a", "doc-1", "Unsafe", "manual", "Security content", "https://user:password@example.com")


def test_chunking_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_document(document(), chunk_size=300, overlap=300)


def test_retrieval_is_relevant_and_tenant_scoped() -> None:
    async def run() -> None:
        engine = KnowledgeEngine(InMemoryKnowledgeStore())
        await engine.ingest(document())
        await engine.ingest(document("tenant-b", "other-doc", "Payroll and employee leave management policy."))
        results = await engine.retrieve(RetrievalRequest("tenant-a", "Linux server vulnerability security update", 5))
        assert results
        assert results[0].chunk.document_id == "cve-2026-1234"
        assert all(item.chunk.tenant_id == "tenant-a" for item in results)
        other = await engine.retrieve(RetrievalRequest("tenant-c", "Linux vulnerability", 5))
        assert other == ()
    asyncio.run(run())


def test_ingestion_upserts_without_duplicate_chunks() -> None:
    async def run() -> None:
        engine = KnowledgeEngine(InMemoryKnowledgeStore())
        count = await engine.ingest(document())
        again = await engine.ingest(document())
        results = await engine.retrieve(RetrievalRequest("tenant-a", "Linux vulnerability"))
        assert count == again
        assert len(results) == count
    asyncio.run(run())


class CapturingSpecialist:
    def __init__(self) -> None:
        self.request: SpecialistRequest | None = None
    async def analyze(self, request: SpecialistRequest) -> SpecialistAnalysis:
        self.request = request
        return SpecialistAnalysis(request.kind, tuple(item.evidence_id for item in request.evidence),
                                  GenerationResult("Advisory only.", "test", "test-model", "stop"))


def test_rag_adds_retrieved_citations_to_same_tenant_analysis() -> None:
    async def run() -> None:
        engine = KnowledgeEngine(InMemoryKnowledgeStore())
        await engine.ingest(document())
        specialist = CapturingSpecialist()
        service = KnowledgeAugmentedSpecialistService(engine, specialist)
        request = SpecialistRequest(
            SpecialistKind.VULNERABILITY_ANALYSIS, "tenant-a", "request-1",
            (EvidenceItem("asset-1", "asset", "Linux server exposed to internet."),),
        )
        result = await service.analyze(request)
        assert specialist.request is not None
        assert specialist.request.tenant_id == "tenant-a"
        assert len(specialist.request.evidence) > 1
        assert any(item.evidence_id.startswith("knowledge:") for item in specialist.request.evidence)
        assert result.requires_human_review is True
    asyncio.run(run())


def test_augmentation_never_adds_another_tenants_knowledge() -> None:
    async def run() -> None:
        engine = KnowledgeEngine(InMemoryKnowledgeStore())
        await engine.ingest(document(tenant_id="tenant-b"))
        specialist = CapturingSpecialist()
        service = KnowledgeAugmentedSpecialistService(engine, specialist)
        request = SpecialistRequest(
            SpecialistKind.ALERT_TRIAGE, "tenant-a", "request-2",
            (EvidenceItem("evt-1", "alert", "Linux service vulnerability detected."),),
        )
        await service.analyze(request)
        assert specialist.request is not None
        assert len(specialist.request.evidence) == 1
    asyncio.run(run())
