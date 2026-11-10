"""Knowledge store contracts and deterministic in-memory development adapter."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from aegis_ai.knowledge.contracts import KnowledgeChunk, KnowledgeMatch, RetrievalRequest

_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._:-]{1,}")


class KnowledgeStore(Protocol):
    """Persistence boundary; every query is scoped to one trusted tenant."""

    async def upsert(self, chunks: tuple[KnowledgeChunk, ...]) -> None: ...

    async def search(self, request: RetrievalRequest) -> tuple[KnowledgeMatch, ...]: ...


class InMemoryKnowledgeStore:
    """Process-local adapter for tests and local development only."""

    def __init__(self) -> None:
        self._chunks: dict[tuple[str, str], KnowledgeChunk] = {}

    async def upsert(self, chunks: tuple[KnowledgeChunk, ...]) -> None:
        for chunk in chunks:
            self._chunks[(chunk.tenant_id, chunk.chunk_id)] = chunk

    async def search(self, request: RetrievalRequest) -> tuple[KnowledgeMatch, ...]:
        query_terms = _tokens(request.query)
        if not query_terms:
            return ()
        tenant_chunks = [
            chunk
            for (tenant_id, _), chunk in self._chunks.items()
            if tenant_id == request.tenant_id
        ]
        if not tenant_chunks:
            return ()
        document_frequency: Counter[str] = Counter()
        tokenized: dict[str, Counter[str]] = {}
        for chunk in tenant_chunks:
            terms = Counter(_tokens(f"{chunk.title} {chunk.source} {chunk.content}"))
            tokenized[chunk.chunk_id] = terms
            document_frequency.update(terms.keys())
        total_documents = len(tenant_chunks)
        query_frequency = Counter(query_terms)
        matches: list[KnowledgeMatch] = []
        for chunk in tenant_chunks:
            terms = tokenized[chunk.chunk_id]
            score = 0.0
            for term, query_count in query_frequency.items():
                frequency = terms.get(term, 0)
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1
                    + (total_documents - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                score += inverse_frequency * (frequency / (frequency + 1.2)) * query_count
            if score > 0:
                matches.append(KnowledgeMatch(chunk=chunk, score=min(score / (score + 2.5), 1.0)))
        matches.sort(key=lambda item: (-item.score, item.chunk.document_id, item.chunk.chunk_index))
        return tuple(matches[: request.top_k])


def _tokens(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(value.lower())
