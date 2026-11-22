"""Validated runtime factory for tenant-bound PostgreSQL knowledge stores."""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_ai.knowledge.embeddings import (
    EmbeddingProvider,
    OpenAICompatibleEmbedder,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.knowledge_config import KnowledgeSettings
from app.ai.knowledge_store import EmbeddingSpaceProfile, PostgresKnowledgeStore
from app.security.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class KnowledgeRuntime:
    """Shared connection/provider resources that create stores per tenant.

    This object is safe to keep on application state: it contains no tenant
    identity or tenant-specific store. Callers must pass a server-resolved
    TenantContext for every store construction.
    """

    runtime_session_factory: async_sessionmaker[AsyncSession]
    ingestor_session_factory: async_sessionmaker[AsyncSession]
    embeddings: EmbeddingProvider = field(repr=False)
    embedding_space: EmbeddingSpaceProfile

    def for_tenant(self, tenant: TenantContext) -> PostgresKnowledgeStore:
        """Create a fresh store bound to one verified tenant context."""

        if not isinstance(tenant, TenantContext):
            raise TypeError("knowledge stores require a verified TenantContext")
        return PostgresKnowledgeStore(
            runtime_session_factory=self.runtime_session_factory,
            ingestor_session_factory=self.ingestor_session_factory,
            subject=tenant.subject,
            tenant_id=tenant.tenant_id,
            embeddings=self.embeddings,
            embedding_space=self.embedding_space,
        )


async def verify_database_role(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    expected_role: str,
) -> None:
    """Verify the connected PostgreSQL identity without leaking connection errors."""

    if expected_role not in {"aegis_runtime", "aegis_ingestor"}:
        raise ValueError("unsupported knowledge database role")

    try:
        async with session_factory() as session:
            actual_role = await session.scalar(text("SELECT current_user"))
    except SQLAlchemyError:
        raise RuntimeError(
            f"knowledge database role verification failed for {expected_role}"
        ) from None

    if actual_role != expected_role:
        raise RuntimeError(
            f"knowledge database role verification failed for {expected_role}"
        )


def build_knowledge_runtime(
    settings: KnowledgeSettings,
    *,
    runtime_session_factory: async_sessionmaker[AsyncSession],
    ingestor_session_factory: async_sessionmaker[AsyncSession],
) -> KnowledgeRuntime:
    """Build provider and embedding identity after database roles are verified."""

    if not settings.enabled:
        raise ValueError("knowledge memory configuration is disabled")
    if settings.embedding_provider != "openai-compatible":
        raise ValueError("unsupported knowledge embedding provider")

    if (
        settings.embedding_model is None
        or settings.embedding_model_revision is None
        or settings.embedding_dimensions is None
        or settings.embedding_api_key is None
    ):
        raise ValueError("knowledge memory configuration is incomplete")

    embeddings = OpenAICompatibleEmbedder(
        base_url=settings.embedding_base_url,
        model=settings.embedding_model,
        api_key=settings.embedding_api_key.get_secret_value(),
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    embedding_space = EmbeddingSpaceProfile(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        model_revision=settings.embedding_model_revision,
        dimensions=settings.embedding_dimensions,
    )
    return KnowledgeRuntime(
        runtime_session_factory=runtime_session_factory,
        ingestor_session_factory=ingestor_session_factory,
        embeddings=embeddings,
        embedding_space=embedding_space,
    )
