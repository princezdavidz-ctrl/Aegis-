"""Immutable contracts for approved security knowledge and retrieval provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class KnowledgeClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A document submitted by a trusted ingestion adapter."""

    tenant_id: str
    document_id: str
    title: str
    source: str
    content: str
    source_uri: str | None = None
    classification: KnowledgeClassification = KnowledgeClassification.PUBLIC
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or len(self.tenant_id) > 128:
            raise ValueError("tenant_id must contain 1–128 characters")
        if not self.document_id.strip() or len(self.document_id) > 160:
            raise ValueError("document_id must contain 1–160 characters")
        if not self.title.strip() or len(self.title) > 240:
            raise ValueError("title must contain 1–240 characters")
        if not self.source.strip() or len(self.source) > 80:
            raise ValueError("source must contain 1–80 characters")
        if not self.content.strip() or len(self.content) > 100_000:
            raise ValueError("content must contain 1–100000 characters")
        if self.source_uri is not None:
            parsed = urlparse(self.source_uri)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("source_uri must be an HTTPS URL without embedded credentials")


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """A bounded document fragment with stable provenance."""

    tenant_id: str
    chunk_id: str
    document_id: str
    title: str
    source: str
    content: str
    chunk_index: int
    source_uri: str | None
    classification: KnowledgeClassification
    updated_at: str | None

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.chunk_id or not self.document_id:
            raise ValueError("tenant_id, chunk_id and document_id are required")
        if not self.content.strip() or len(self.content) > 2_000:
            raise ValueError("chunk content must contain 1–2000 characters")
        if self.chunk_index < 0:
            raise ValueError("chunk_index cannot be negative")


@dataclass(frozen=True, slots=True)
class KnowledgeMatch:
    """A retrieved chunk and its retrieval score."""

    chunk: KnowledgeChunk
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("retrieval score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """A query whose tenant scope must come from authenticated server context."""

    tenant_id: str
    query: str
    top_k: int = 5

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.query.strip() or len(self.query) > 4_000:
            raise ValueError("query must contain 1–4000 characters")
        if not 1 <= self.top_k <= 10:
            raise ValueError("top_k must be between 1 and 10")
