"""Tenant-bound PostgreSQL/pgvector adapter for the AI KnowledgeStore protocol."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from aegis_ai.knowledge.contracts import (
    KnowledgeChunk,
    KnowledgeClassification,
    KnowledgeMatch,
    RetrievalRequest,
)
from aegis_ai.knowledge.embeddings import EmbeddingProvider
from aegis_ai.knowledge.store import KnowledgeStore
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import apply_database_context


@dataclass(frozen=True, slots=True)
class EmbeddingSpaceProfile:
    """Immutable identity for one provider/model/revision/vector dimension space."""

    provider: str
    model: str
    model_revision: str
    dimensions: int

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("provider", self.provider, 80),
            ("model", self.model, 160),
            ("model_revision", self.model_revision, 120),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"{name} must contain 1–{maximum} characters")
        if (
            isinstance(self.dimensions, bool)
            or not isinstance(self.dimensions, int)
            or not 1 <= self.dimensions <= 16_000
        ):
            raise ValueError("dimensions must be between 1 and 16000")


class KnowledgeStoreConflict(RuntimeError):
    """An immutable document key was reused for different source content."""


class PostgresKnowledgeStore(KnowledgeStore):
    """PostgreSQL adapter bound to one verified subject and one tenant.

    The runtime factory must use the read-only aegis_runtime role. The ingestor
    factory must use aegis_ingestor. Each operation owns a fresh transaction
    and sets transaction-local RLS context before accessing knowledge rows.
    """

    def __init__(
        self,
        *,
        runtime_session_factory: async_sessionmaker[AsyncSession],
        ingestor_session_factory: async_sessionmaker[AsyncSession],
        subject: str,
        tenant_id: UUID,
        embeddings: EmbeddingProvider,
        embedding_space: EmbeddingSpaceProfile,
    ) -> None:
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 128:
            raise ValueError("subject must contain 1–128 characters")
        if not isinstance(tenant_id, UUID):
            raise TypeError("tenant_id must be a server-resolved UUID")
        if embeddings.dimensions != embedding_space.dimensions:
            raise ValueError("embedding provider dimensions do not match the embedding space")
        self._runtime_sessions = runtime_session_factory
        self._ingestor_sessions = ingestor_session_factory
        self._subject = subject
        self._tenant_id = tenant_id
        self._embeddings = embeddings
        self._space = embedding_space

    async def upsert(self, chunks: tuple[KnowledgeChunk, ...]) -> None:
        """Persist one immutable document version and its embeddings atomically."""
        if not chunks:
            return
        ordered = tuple(sorted(chunks, key=lambda item: item.chunk_index))
        self._validate_document_chunks(ordered)

        vectors: list[tuple[float, ...]] = []
        for offset in range(0, len(ordered), 64):
            batch = ordered[offset : offset + 64]
            embedded = await self._embeddings.embed(tuple(item.content for item in batch))
            if len(embedded) != len(batch):
                raise ValueError("embedding provider returned an unexpected vector count")
            vectors.extend(self._validate_vector(vector) for vector in embedded)

        document = ordered[0]
        document_digest = hashlib.sha256(
            "\n".join(item.content for item in ordered).encode("utf-8")
        ).hexdigest()
        updated_at = self._parse_updated_at(document.updated_at)

        async with self._ingestor_sessions() as session, session.begin():
            await apply_database_context(
                session,
                subject=self._subject,
                tenant_id=self._tenant_id,
            )
            space_id = await self._ensure_embedding_space(session)
            document_id = await self._ensure_document(
                session,
                document=document,
                content_sha256=document_digest,
                updated_at=updated_at,
            )
            for chunk, vector in zip(ordered, vectors, strict=True):
                await session.execute(
                    text(
                        """
                        INSERT INTO public.knowledge_chunks (
                            tenant_id, document_id, chunk_key, chunk_index,
                            content, content_sha256, embedding_space_id,
                            embedding_dimensions, embedding
                        )
                        VALUES (
                            :tenant_id, :document_id, :chunk_key, :chunk_index,
                            :content, :content_sha256, :space_id,
                            :dimensions, CAST(:embedding AS vector)
                        )
                        ON CONFLICT (
                            tenant_id, document_id, chunk_key, embedding_space_id
                        ) DO NOTHING
                        """
                    ),
                    {
                        "tenant_id": self._tenant_id,
                        "document_id": document_id,
                        "chunk_key": chunk.chunk_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "content_sha256": self._digest(chunk.content),
                        "space_id": space_id,
                        "dimensions": self._space.dimensions,
                        "embedding": self._vector_literal(vector),
                    },
                )

    async def search(self, request: RetrievalRequest) -> tuple[KnowledgeMatch, ...]:
        """Run tenant- and embedding-space-scoped hybrid retrieval."""
        requested_tenant = self._parse_tenant_id(request.tenant_id)
        if requested_tenant != self._tenant_id:
            raise PermissionError("knowledge store is bound to a different tenant")

        async with self._runtime_sessions() as session, session.begin():
            await apply_database_context(
                session,
                subject=self._subject,
                tenant_id=self._tenant_id,
            )
            space_id = await session.scalar(
                text(
                    """
                    SELECT id
                    FROM public.knowledge_embedding_spaces
                    WHERE tenant_id = :tenant_id
                      AND provider = :provider
                      AND model = :model
                      AND model_revision = :model_revision
                      AND dimensions = :dimensions
                    """
                ),
                {
                    "tenant_id": self._tenant_id,
                    "provider": self._space.provider,
                    "model": self._space.model,
                    "model_revision": self._space.model_revision,
                    "dimensions": self._space.dimensions,
                },
            )
        if space_id is None:
            return ()

        embedded = await self._embeddings.embed((request.query,))
        if len(embedded) != 1:
            raise ValueError("embedding provider returned an unexpected query vector count")
        query_vector = self._validate_vector(embedded[0])
        candidate_limit = min(50, max(request.top_k, request.top_k * 5))

        async with self._runtime_sessions() as session, session.begin():
            await apply_database_context(
                session,
                subject=self._subject,
                tenant_id=self._tenant_id,
            )
            result = await session.execute(
                text(
                    """
                    WITH vector_candidates AS (
                        SELECT candidate.id,
                               ROW_NUMBER() OVER (
                                   ORDER BY candidate.distance,
                                            candidate.document_id,
                                            candidate.chunk_index
                               ) AS rank
                        FROM (
                            SELECT chunk.id,
                                   chunk.document_id,
                                   chunk.chunk_index,
                                   chunk.embedding <=> CAST(:embedding AS vector)
                                       AS distance
                            FROM public.knowledge_chunks AS chunk
                            JOIN public.knowledge_documents AS document
                              ON document.tenant_id = chunk.tenant_id
                             AND document.id = chunk.document_id
                            WHERE chunk.tenant_id = :tenant_id
                              AND chunk.embedding_space_id = :space_id
                              AND document.classification IN ('public', 'internal')
                            ORDER BY distance, chunk.document_id, chunk.chunk_index
                            LIMIT :candidate_limit
                        ) AS candidate
                    ),
                    lexical_candidates AS (
                        SELECT candidate.id,
                               ROW_NUMBER() OVER (
                                   ORDER BY candidate.lexical_score DESC,
                                            candidate.document_id,
                                            candidate.chunk_index
                               ) AS rank
                        FROM (
                            SELECT chunk.id,
                                   chunk.document_id,
                                   chunk.chunk_index,
                                   ts_rank_cd(
                                       chunk.search_vector,
                                       plainto_tsquery('simple', :query)
                                   ) AS lexical_score
                            FROM public.knowledge_chunks AS chunk
                            JOIN public.knowledge_documents AS document
                              ON document.tenant_id = chunk.tenant_id
                             AND document.id = chunk.document_id
                            WHERE chunk.tenant_id = :tenant_id
                              AND chunk.embedding_space_id = :space_id
                              AND document.classification IN ('public', 'internal')
                              AND chunk.search_vector @@ plainto_tsquery('simple', :query)
                            ORDER BY lexical_score DESC,
                                     chunk.document_id,
                                     chunk.chunk_index
                            LIMIT :candidate_limit
                        ) AS candidate
                    ),
                    combined_ranks AS (
                        SELECT id, SUM(contribution) AS reciprocal_rank
                        FROM (
                            SELECT id, 1.0 / (60.0 + rank) AS contribution
                            FROM vector_candidates
                            UNION ALL
                            SELECT id, 1.0 / (60.0 + rank) AS contribution
                            FROM lexical_candidates
                        ) AS ranked_sources
                        GROUP BY id
                    )
                    SELECT
                        chunk.tenant_id,
                        document.document_key,
                        chunk.chunk_key,
                        document.title,
                        document.source,
                        chunk.content,
                        chunk.chunk_index,
                        document.source_uri,
                        document.classification,
                        document.updated_at,
                        LEAST(
                            combined_ranks.reciprocal_rank / (2.0 / 61.0),
                            1.0
                        ) AS score
                    FROM combined_ranks
                    JOIN public.knowledge_chunks AS chunk
                      ON chunk.id = combined_ranks.id
                     AND chunk.tenant_id = :tenant_id
                     AND chunk.embedding_space_id = :space_id
                    JOIN public.knowledge_documents AS document
                      ON document.tenant_id = chunk.tenant_id
                     AND document.id = chunk.document_id
                    ORDER BY combined_ranks.reciprocal_rank DESC,
                             document.document_key,
                             chunk.chunk_index
                    LIMIT :top_k
                    """
                ),
                {
                    "tenant_id": self._tenant_id,
                    "space_id": space_id,
                    "embedding": self._vector_literal(query_vector),
                    "query": request.query,
                    "candidate_limit": candidate_limit,
                    "top_k": request.top_k,
                },
            )
            rows = result.mappings().all()

        matches: list[KnowledgeMatch] = []
        for row in rows:
            updated = row["updated_at"]
            matches.append(
                KnowledgeMatch(
                    chunk=KnowledgeChunk(
                        tenant_id=str(row["tenant_id"]),
                        chunk_id=row["chunk_key"],
                        document_id=row["document_key"],
                        title=row["title"],
                        source=row["source"],
                        content=row["content"],
                        chunk_index=row["chunk_index"],
                        source_uri=row["source_uri"],
                        classification=KnowledgeClassification(row["classification"]),
                        updated_at=updated.isoformat() if updated is not None else None,
                    ),
                    score=max(0.0, min(1.0, float(row["score"]))),
                )
            )
        return tuple(matches)

    async def _ensure_embedding_space(self, session: AsyncSession) -> UUID:
        await session.execute(
            text(
                """
                INSERT INTO public.knowledge_embedding_spaces (
                    tenant_id, provider, model, model_revision, dimensions
                )
                VALUES (
                    :tenant_id, :provider, :model, :model_revision, :dimensions
                )
                ON CONFLICT (
                    tenant_id, provider, model, model_revision, dimensions
                ) DO NOTHING
                """
            ),
            {
                "tenant_id": self._tenant_id,
                "provider": self._space.provider,
                "model": self._space.model,
                "model_revision": self._space.model_revision,
                "dimensions": self._space.dimensions,
            },
        )
        space_id = await session.scalar(
            text(
                """
                SELECT id
                FROM public.knowledge_embedding_spaces
                WHERE tenant_id = :tenant_id
                  AND provider = :provider
                  AND model = :model
                  AND model_revision = :model_revision
                  AND dimensions = :dimensions
                """
            ),
            {
                "tenant_id": self._tenant_id,
                "provider": self._space.provider,
                "model": self._space.model,
                "model_revision": self._space.model_revision,
                "dimensions": self._space.dimensions,
            },
        )
        if space_id is None:
            raise PermissionError("embedding space is not available to this subject")
        return space_id

    async def _ensure_document(
        self,
        session: AsyncSession,
        *,
        document: KnowledgeChunk,
        content_sha256: str,
        updated_at: datetime | None,
    ) -> UUID:
        await session.execute(
            text(
                """
                INSERT INTO public.knowledge_documents (
                    tenant_id, document_key, title, source, source_uri,
                    classification, content_sha256, updated_at
                )
                VALUES (
                    :tenant_id, :document_key, :title, :source, :source_uri,
                    :classification, :content_sha256, :updated_at
                )
                ON CONFLICT (tenant_id, document_key) DO NOTHING
                """
            ),
            {
                "tenant_id": self._tenant_id,
                "document_key": document.document_id,
                "title": document.title,
                "source": document.source,
                "source_uri": document.source_uri,
                "classification": document.classification.value,
                "content_sha256": content_sha256,
                "updated_at": updated_at,
            },
        )
        row = (
            await session.execute(
                text(
                    """
                    SELECT id, content_sha256
                    FROM public.knowledge_documents
                    WHERE tenant_id = :tenant_id
                      AND document_key = :document_key
                    """
                ),
                {
                    "tenant_id": self._tenant_id,
                    "document_key": document.document_id,
                },
            )
        ).mappings().one_or_none()
        if row is None:
            raise PermissionError("document is not available to this subject")
        if row["content_sha256"] != content_sha256:
            raise KnowledgeStoreConflict(
                "document key already exists with different content; use a new versioned document_id"
            )
        document_id = row["id"]
        await session.execute(
            text(
                """
                UPDATE public.knowledge_documents
                SET title = :title,
                    source = :source,
                    source_uri = :source_uri,
                    classification = :classification,
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id
                  AND id = :document_id
                  AND (
                      title IS DISTINCT FROM :title
                      OR source IS DISTINCT FROM :source
                      OR source_uri IS DISTINCT FROM :source_uri
                      OR classification IS DISTINCT FROM :classification
                      OR updated_at IS DISTINCT FROM :updated_at
                  )
                """
            ),
            {
                "tenant_id": self._tenant_id,
                "document_id": document_id,
                "title": document.title,
                "source": document.source,
                "source_uri": document.source_uri,
                "classification": document.classification.value,
                "updated_at": updated_at,
            },
        )
        return document_id

    def _validate_document_chunks(self, chunks: tuple[KnowledgeChunk, ...]) -> None:
        first = chunks[0]
        if self._parse_tenant_id(first.tenant_id) != self._tenant_id:
            raise PermissionError("chunk tenant does not match the bound tenant")
        if not 1 <= len(chunks) <= 128:
            raise ValueError("document must contain 1–128 chunks")
        if not first.document_id or len(first.document_id) > 160:
            raise ValueError("document_id must contain 1–160 characters")
        if not first.title.strip() or len(first.title) > 240:
            raise ValueError("title must contain 1–240 characters")
        if not first.source.strip() or len(first.source) > 80:
            raise ValueError("source must contain 1–80 characters")
        if not isinstance(first.classification, KnowledgeClassification):
            raise TypeError("classification must be a KnowledgeClassification")
        indices = [item.chunk_index for item in chunks]
        if indices != list(range(len(chunks))):
            raise ValueError("chunk indices must be contiguous and start at zero")
        chunk_ids: set[str] = set()
        for item in chunks:
            if self._parse_tenant_id(item.tenant_id) != self._tenant_id:
                raise PermissionError("chunk tenant does not match the bound tenant")
            if (
                item.document_id != first.document_id
                or item.title != first.title
                or item.source != first.source
                or item.source_uri != first.source_uri
                or item.classification != first.classification
                or item.updated_at != first.updated_at
            ):
                raise ValueError("all chunks must belong to the same document version")
            if not item.chunk_id or len(item.chunk_id) > 160:
                raise ValueError("chunk_id must contain 1–160 characters")
            if item.chunk_id in chunk_ids:
                raise ValueError("chunk identifiers must be unique")
            chunk_ids.add(item.chunk_id)
            if not item.content.strip() or len(item.content) > 2_000:
                raise ValueError("chunk content must contain 1–2000 characters")
        self._parse_updated_at(first.updated_at)

    @staticmethod
    def _parse_tenant_id(value: str) -> UUID:
        try:
            return UUID(value)
        except (AttributeError, TypeError, ValueError):
            raise ValueError("tenant_id must be a UUID") from None

    @staticmethod
    def _parse_updated_at(value: str | None) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("updated_at must be an ISO-8601 string")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("updated_at must be a valid ISO-8601 timestamp") from None
        if parsed.tzinfo is None:
            raise ValueError("updated_at must include a timezone")
        return parsed.astimezone(UTC)

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _validate_vector(self, vector: Sequence[float]) -> tuple[float, ...]:
        if isinstance(vector, (str, bytes)) or len(vector) != self._space.dimensions:
            raise ValueError("embedding vector dimensions do not match the configured space")
        values: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("embedding vector values must be numeric")
            converted = float(value)
            if not math.isfinite(converted):
                raise ValueError("embedding vector values must be finite")
            values.append(converted)
        if not any(value != 0.0 for value in values):
            raise ValueError("embedding vector cannot be all zero")
        return tuple(values)

    @staticmethod
    def _vector_literal(vector: tuple[float, ...]) -> str:
        return "[" + ",".join(format(value, ".17g") for value in vector) + "]"
