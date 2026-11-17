"""Tenant-scoped security knowledge ingestion and retrieval."""

from aegis_ai.knowledge.contracts import (
    KnowledgeChunk,
    KnowledgeClassification,
    KnowledgeDocument,
    KnowledgeMatch,
    RetrievalRequest,
)
from aegis_ai.knowledge.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    OpenAICompatibleEmbedder,
)
from aegis_ai.knowledge.engine import KnowledgeEngine
from aegis_ai.knowledge.store import InMemoryKnowledgeStore, KnowledgeStore

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "InMemoryKnowledgeStore",
    "KnowledgeChunk",
    "KnowledgeClassification",
    "KnowledgeDocument",
    "KnowledgeEngine",
    "KnowledgeMatch",
    "KnowledgeStore",
    "OpenAICompatibleEmbedder",
    "RetrievalRequest",
]
