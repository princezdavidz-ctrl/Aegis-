"""Security knowledge ingestion and retrieval orchestration."""

from __future__ import annotations

from aegis_ai.knowledge.chunking import chunk_document
from aegis_ai.knowledge.contracts import KnowledgeDocument, KnowledgeMatch, RetrievalRequest
from aegis_ai.knowledge.store import KnowledgeStore


class KnowledgeEngine:
    """Ingest approved documents and retrieve tenant-scoped supporting context."""

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    async def ingest(self, document: KnowledgeDocument) -> int:
        chunks = chunk_document(document)
        await self._store.upsert(chunks)
        return len(chunks)

    async def retrieve(self, request: RetrievalRequest) -> tuple[KnowledgeMatch, ...]:
        return await self._store.search(request)
