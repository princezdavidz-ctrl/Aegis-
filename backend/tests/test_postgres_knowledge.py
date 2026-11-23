"""PostgreSQL integration tests for persistent knowledge schema and tenant RLS."""

from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import pytest
from aegis_ai.knowledge import (
    KnowledgeClassification,
    KnowledgeDocument,
    KnowledgeEngine,
    RetrievalRequest,
)
from app.ai.knowledge_store import (
    EmbeddingSpaceProfile,
    KnowledgeStoreConflict,
    PostgresKnowledgeStore,
)
from app.db.session import apply_database_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ADMIN_URL = os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
RUNTIME_URL = os.getenv("AEGIS_TEST_DATABASE_URL")
PROVISIONER_URL = os.getenv("AEGIS_TEST_PROVISIONER_DATABASE_URL")
INGESTOR_URL = os.getenv("AEGIS_TEST_INGESTOR_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not all((ADMIN_URL, RUNTIME_URL, PROVISIONER_URL, INGESTOR_URL)),
    reason="PostgreSQL knowledge-store integration URLs are not configured",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_knowledge_schema_enforces_tenant_scope_and_embedding_compatibility() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    runtime_engine = create_async_engine(RUNTIME_URL)
    provisioner_engine = create_async_engine(PROVISIONER_URL)
    ingestor_engine = create_async_engine(INGESTOR_URL)

    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    provisioner_factory = async_sessionmaker(provisioner_engine, expire_on_commit=False)
    ingestor_factory = async_sessionmaker(ingestor_engine, expire_on_commit=False)

    actor_a = "oidc|knowledge-admin-a"
    actor_b = "oidc|knowledge-admin-b"
    request_id = uuid4()
    slug_prefix = f"knowledge-{request_id.hex[:10]}"

    async def provision(session_factory, slug: str, actor: str):
        async with session_factory() as session:
            tenant_id = (
                await session.execute(
                    text("""
                        SELECT tenant_id FROM public.aegis_provision_tenant(
                            :slug, :display_name, :actor, :actor, 'user', :request_id
                        )
                    """),
                    {
                        "slug": slug,
                        "display_name": slug,
                        "actor": actor,
                        "request_id": uuid4(),
                    },
                )
            ).scalar_one()
            await session.commit()
            return tenant_id

    async def seed(tenant_id, actor: str, key: str):
        space_id = uuid4()
        document_id = uuid4()
        chunk_id = uuid4()
        content = f"Tenant {key} security baseline and endpoint hardening guidance."
        async with ingestor_factory() as session:
            await apply_database_context(session, subject=actor, tenant_id=tenant_id)
            await session.execute(
                text("""
                    INSERT INTO public.knowledge_embedding_spaces
                        (id, tenant_id, provider, model, model_revision, dimensions)
                    VALUES
                        (:id, :tenant_id, 'test-provider', 'test-embedding', 'revision-1', 3)
                """),
                {"id": space_id, "tenant_id": tenant_id},
            )
            await session.execute(
                text("""
                    INSERT INTO public.knowledge_documents
                        (id, tenant_id, document_key, title, source, source_uri,
                         classification, content_sha256)
                    VALUES
                        (:id, :tenant_id, :document_key, :title, 'security-baseline',
                         'https://security.example/baseline', 'internal', :content_sha256)
                """),
                {
                    "id": document_id,
                    "tenant_id": tenant_id,
                    "document_key": f"baseline-{key}",
                    "title": f"Tenant {key} baseline",
                    "content_sha256": _digest(content),
                },
            )
            await session.execute(
                text("""
                    INSERT INTO public.knowledge_chunks
                        (id, tenant_id, document_id, chunk_key, chunk_index, content,
                         content_sha256, embedding_space_id, embedding_dimensions, embedding)
                    VALUES
                        (:id, :tenant_id, :document_id, :chunk_key, 0, :content,
                         :content_sha256, :space_id, 3, CAST(:embedding AS vector))
                """),
                {
                    "id": chunk_id,
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "chunk_key": f"chunk-{key}",
                    "content": content,
                    "content_sha256": _digest(content),
                    "space_id": space_id,
                    "embedding": "[0.1,0.2,0.3]",
                },
            )
            await session.commit()
        return space_id, document_id, chunk_id

    try:
        tenant_a = await provision(provisioner_factory, f"{slug_prefix}-a", actor_a)
        tenant_b = await provision(provisioner_factory, f"{slug_prefix}-b", actor_b)
        space_a, document_a, chunk_a = await seed(tenant_a, actor_a, "a")
        space_b, document_b, _ = await seed(tenant_b, actor_b, "b")

        async with runtime_factory() as session:
            await apply_database_context(session, subject=actor_a, tenant_id=tenant_a)
            documents = (
                await session.execute(
                    text("SELECT id FROM public.knowledge_documents ORDER BY id")
                )
            ).scalars().all()
            chunks = (
                await session.execute(
                    text("""
                        SELECT id, vector_dims(embedding) AS dimensions
                        FROM public.knowledge_chunks
                        ORDER BY id
                    """)
                )
            ).all()
            assert documents == [document_a]
            assert len(chunks) == 1
            assert chunks[0].id == chunk_a
            assert chunks[0].dimensions == 3

        async with runtime_factory() as session:
            # A valid tenant UUID alone is insufficient: this subject has no
            # active membership in tenant B.
            await apply_database_context(session, subject=actor_a, tenant_id=tenant_b)
            documents = (
                await session.execute(
                    text("SELECT id FROM public.knowledge_documents")
                )
            ).scalars().all()
            chunks = (
                await session.execute(
                    text("SELECT id FROM public.knowledge_chunks")
                )
            ).scalars().all()
            assert documents == []
            assert chunks == []

        async with ingestor_factory() as session:
            await apply_database_context(session, subject=actor_a, tenant_id=tenant_a)
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("""
                        INSERT INTO public.knowledge_documents
                            (id, tenant_id, document_key, title, source, classification,
                             content_sha256)
                        VALUES
                            (:id, :tenant_id, 'forbidden', 'Forbidden', 'test', 'internal', :digest)
                    """),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_b,
                        "digest": _digest("forbidden"),
                    },
                )
            await session.rollback()

        async with ingestor_factory() as session:
            await apply_database_context(session, subject=actor_a, tenant_id=tenant_a)
            # Composite tenant/document FK prevents attaching another tenant's
            # document to a chunk even when the caller has a valid tenant-A context.
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("""
                        INSERT INTO public.knowledge_chunks
                            (tenant_id, document_id, chunk_key, chunk_index, content,
                             content_sha256, embedding_space_id, embedding_dimensions, embedding)
                        VALUES
                            (:tenant_id, :document_id, 'cross-tenant-document', 1, 'Mismatch',
                             :digest, :space_id, 3, CAST('[0.1,0.2,0.3]' AS vector))
                    """),
                    {
                        "tenant_id": tenant_a,
                        "document_id": document_b,
                        "digest": _digest("Mismatch"),
                        "space_id": space_a,
                    },
                )
            await session.rollback()

        async with ingestor_factory() as session:
            await apply_database_context(session, subject=actor_a, tenant_id=tenant_a)
            # Composite tenant/space FK prevents vectors from crossing embedding spaces.
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("""
                        INSERT INTO public.knowledge_chunks
                            (tenant_id, document_id, chunk_key, chunk_index, content,
                             content_sha256, embedding_space_id, embedding_dimensions, embedding)
                        VALUES
                            (:tenant_id, :document_id, 'cross-tenant-space', 1, 'Mismatch',
                             :digest, :space_id, 3, CAST('[0.1,0.2,0.3]' AS vector))
                    """),
                    {
                        "tenant_id": tenant_a,
                        "document_id": document_a,
                        "digest": _digest("Mismatch"),
                        "space_id": space_b,
                    },
                )
            await session.rollback()

        async with ingestor_factory() as session:
            await apply_database_context(session, subject=actor_a, tenant_id=tenant_a)
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("""
                        INSERT INTO public.knowledge_chunks
                            (tenant_id, document_id, chunk_key, chunk_index, content,
                             content_sha256, embedding_space_id, embedding_dimensions, embedding)
                        VALUES
                            (:tenant_id, :document_id, 'wrong-dimensions', 1, 'Mismatch',
                             :digest, :space_id, 3, CAST('[0.1,0.2]' AS vector))
                    """),
                    {
                        "tenant_id": tenant_a,
                        "document_id": document_a,
                        "digest": _digest("Mismatch"),
                        "space_id": space_a,
                    },
                )
            await session.rollback()

        async with admin_factory() as session:
            privileges = (
                await session.execute(
                    text("""
                        SELECT
                            has_table_privilege('aegis_runtime', 'knowledge_chunks', 'SELECT'),
                            has_table_privilege('aegis_runtime', 'knowledge_chunks', 'INSERT'),
                            has_table_privilege('aegis_ingestor', 'knowledge_chunks', 'INSERT'),
                            has_table_privilege('aegis_ingestor', 'knowledge_chunks', 'DELETE'),
                            has_table_privilege('aegis_ingestor', 'tenant_memberships', 'SELECT'),
                            has_table_privilege('aegis_ingestor', 'audit_events', 'INSERT'),
                            has_table_privilege('aegis_ingestor', 'knowledge_embedding_spaces', 'UPDATE')
                    """)
                )
            ).one()
            assert privileges == (True, False, True, False, True, False, False)

            audit = (
                await session.execute(
                    text("""
                        SELECT resource_type, action
                        FROM public.audit_events
                        WHERE tenant_id = :tenant_id
                          AND resource_type IN ('knowledge_document', 'knowledge_chunk')
                    """),
                    {"tenant_id": tenant_a},
                )
            ).all()
            assert ("knowledge_document", "knowledge.document.create") in audit
            assert ("knowledge_chunk", "knowledge.chunk.create") in audit
    finally:
        await ingestor_engine.dispose()
        await provisioner_engine.dispose()
        await runtime_engine.dispose()
        await admin_engine.dispose()


class FixedEmbeddingProvider:
    """Deterministic local embedding fake; no provider credentials or network calls."""

    dimensions = 3

    async def embed(self, texts):
        return tuple((1.0, 0.25, 0.0) for _ in texts)


@pytest.mark.asyncio
async def test_postgres_knowledge_store_is_idempotent_tenant_bound_and_classified() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    runtime_engine = create_async_engine(RUNTIME_URL)
    provisioner_engine = create_async_engine(PROVISIONER_URL)
    ingestor_engine = create_async_engine(INGESTOR_URL)

    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    provisioner_factory = async_sessionmaker(provisioner_engine, expire_on_commit=False)
    ingestor_factory = async_sessionmaker(ingestor_engine, expire_on_commit=False)

    actor_a = "oidc|knowledge-adapter-a"
    actor_b = "oidc|knowledge-adapter-b"
    request_id = uuid4()
    slug_prefix = f"knowledge-adapter-{request_id.hex[:8]}"
    profile = EmbeddingSpaceProfile(
        provider="test-provider",
        model="test-embedding",
        model_revision="revision-1",
        dimensions=3,
    )
    embeddings = FixedEmbeddingProvider()

    async def provision(slug: str, actor: str):
        async with provisioner_factory() as session:
            tenant_id = (
                await session.execute(
                    text("""
                        SELECT tenant_id FROM public.aegis_provision_tenant(
                            :slug, :display_name, :actor, :actor, 'user', :request_id
                        )
                    """),
                    {
                        "slug": slug,
                        "display_name": slug,
                        "actor": actor,
                        "request_id": uuid4(),
                    },
                )
            ).scalar_one()
            await session.commit()
            return tenant_id

    async def add_active_member(
        tenant_id,
        tenant_slug: str,
        admin_subject: str,
        member_subject: str,
        role: str,
    ) -> None:
        async with provisioner_factory() as session:
            await session.execute(
                text("""
                    SELECT * FROM public.aegis_manage_tenant_member(
                        :tenant_id, :target_subject, :target_role, 'invite',
                        :actor_subject, 'user', :request_id
                    )
                """),
                {
                    "tenant_id": tenant_id,
                    "target_subject": member_subject,
                    "target_role": role,
                    "actor_subject": admin_subject,
                    "request_id": uuid4(),
                },
            )
            await session.commit()
        async with provisioner_factory() as session:
            await session.execute(
                text("""
                    SELECT * FROM public.aegis_accept_tenant_invitation(
                        :tenant_slug, :actor_subject, :request_id
                    )
                """),
                {
                    "tenant_slug": tenant_slug,
                    "actor_subject": member_subject,
                    "request_id": uuid4(),
                },
            )
            await session.commit()

    def store_for(tenant_id, actor: str) -> PostgresKnowledgeStore:
        return PostgresKnowledgeStore(
            runtime_session_factory=runtime_factory,
            ingestor_session_factory=ingestor_factory,
            subject=actor,
            tenant_id=tenant_id,
            embeddings=embeddings,
            embedding_space=profile,
        )

    try:
        tenant_a_slug = f"{slug_prefix}-a"
        tenant_b_slug = f"{slug_prefix}-b"
        tenant_a = await provision(tenant_a_slug, actor_a)
        tenant_b = await provision(tenant_b_slug, actor_b)
        viewer_subject = "oidc|knowledge-adapter-viewer"
        security_manager_subject = "oidc|knowledge-adapter-security-manager"
        await add_active_member(
            tenant_a, tenant_a_slug, actor_a, viewer_subject, "viewer"
        )
        await add_active_member(
            tenant_a, tenant_a_slug, actor_a, security_manager_subject, "security_manager"
        )
        engine_a = KnowledgeEngine(store_for(tenant_a, actor_a))
        engine_b = KnowledgeEngine(store_for(tenant_b, actor_b))
        engine_viewer = KnowledgeEngine(store_for(tenant_a, viewer_subject))
        engine_security_manager = KnowledgeEngine(
            store_for(tenant_a, security_manager_subject)
        )

        public_document = KnowledgeDocument(
            tenant_id=str(tenant_a),
            document_id="baseline-a",
            title="Linux endpoint hardening",
            source="security-baseline",
            content=(
                "Linux endpoint hardening requires supported package versions, "
                "restricted remote access, strong authentication and monitored logs."
            ),
            source_uri="https://security.example/baselines/linux",
            classification=KnowledgeClassification.PUBLIC,
            updated_at="2026-11-19T00:00:00Z",
        )
        first_count = await engine_a.ingest(public_document)
        second_count = await engine_a.ingest(public_document)
        assert first_count == second_count

        await engine_a.ingest(
            KnowledgeDocument(
                tenant_id=str(tenant_a),
                document_id="restricted-a",
                title="Restricted incident response notes",
                source="incident-notes",
                content="Restricted internal incident response evidence and access details.",
                classification=KnowledgeClassification.RESTRICTED,
            )
        )
        await engine_b.ingest(
            KnowledgeDocument(
                tenant_id=str(tenant_b),
                document_id="baseline-b",
                title="Database backup policy",
                source="security-baseline",
                content="Database backup encryption and recovery testing policy.",
                classification=KnowledgeClassification.PUBLIC,
            )
        )

        results = await engine_a.retrieve(
            RetrievalRequest(str(tenant_a), "Linux endpoint hardening authentication", 5)
        )
        assert results
        assert {item.chunk.document_id for item in results} == {"baseline-a", "restricted-a"}
        assert all(item.chunk.tenant_id == str(tenant_a) for item in results)
        assert any(
            item.chunk.classification == KnowledgeClassification.RESTRICTED
            for item in results
        )

        viewer_results = await engine_viewer.retrieve(
            RetrievalRequest(str(tenant_a), "Linux endpoint hardening authentication", 5)
        )
        assert {item.chunk.document_id for item in viewer_results} == {"baseline-a"}
        assert all(
            item.chunk.classification != KnowledgeClassification.RESTRICTED
            for item in viewer_results
        )

        manager_results = await engine_security_manager.retrieve(
            RetrievalRequest(str(tenant_a), "incident response access details", 5)
        )
        assert "restricted-a" in {item.chunk.document_id for item in manager_results}

        async def visible_rows(subject: str) -> tuple[list[str], int]:
            async with runtime_factory() as session:
                await apply_database_context(session, subject=subject, tenant_id=tenant_a)
                document_keys = (
                    await session.execute(
                        text("""
                            SELECT document_key
                            FROM public.knowledge_documents
                            ORDER BY document_key
                        """)
                    )
                ).scalars().all()
                chunk_count = await session.scalar(
                    text("SELECT count(*) FROM public.knowledge_chunks")
                )
                return document_keys, int(chunk_count or 0)

        assert await visible_rows(viewer_subject) == (["baseline-a"], 1)
        assert await visible_rows(security_manager_subject) == (
            ["baseline-a", "restricted-a"],
            2,
        )

        with pytest.raises(DBAPIError):
            await engine_viewer.ingest(
                KnowledgeDocument(
                    tenant_id=str(tenant_a),
                    document_id="restricted-viewer-write",
                    title="Unauthorized restricted ingestion",
                    source="incident-notes",
                    content="A viewer must not write restricted security evidence.",
                    classification=KnowledgeClassification.RESTRICTED,
                )
            )

        # Classification access is checked against the live membership row, not
        # a cached role carried by the store. A role downgrade takes effect at once.
        async with provisioner_factory() as session:
            await session.execute(
                text("""
                    SELECT * FROM public.aegis_manage_tenant_member(
                        :tenant_id, :target_subject, 'viewer', 'change_role',
                        :actor_subject, 'user', :request_id
                    )
                """),
                {
                    "tenant_id": tenant_a,
                    "target_subject": security_manager_subject,
                    "actor_subject": actor_a,
                    "request_id": uuid4(),
                },
            )
            await session.commit()

        downgraded_results = await engine_security_manager.retrieve(
            RetrievalRequest(str(tenant_a), "incident response access details", 5)
        )
        assert "restricted-a" not in {
            item.chunk.document_id for item in downgraded_results
        }

        with pytest.raises(PermissionError):
            await engine_a.retrieve(
                RetrievalRequest(str(tenant_b), "Database backup policy", 5)
            )

        changed_version = KnowledgeDocument(
            tenant_id=str(tenant_a),
            document_id="baseline-a",
            title="Linux endpoint hardening",
            source="security-baseline",
            content="Changed source content must not silently overwrite an immutable document key.",
            source_uri="https://security.example/baselines/linux",
            classification=KnowledgeClassification.PUBLIC,
            updated_at="2026-11-19T00:00:00Z",
        )
        with pytest.raises(KnowledgeStoreConflict):
            await engine_a.ingest(changed_version)

        unsafe_runtime_store = PostgresKnowledgeStore(
            runtime_session_factory=admin_factory,
            ingestor_session_factory=ingestor_factory,
            subject=actor_a,
            tenant_id=tenant_a,
            embeddings=embeddings,
            embedding_space=profile,
        )
        with pytest.raises(PermissionError, match="aegis_runtime"):
            await unsafe_runtime_store.search(
                RetrievalRequest(str(tenant_a), "Linux endpoint hardening", 5)
            )

        unsafe_ingestor_store = PostgresKnowledgeStore(
            runtime_session_factory=runtime_factory,
            ingestor_session_factory=admin_factory,
            subject=actor_a,
            tenant_id=tenant_a,
            embeddings=embeddings,
            embedding_space=profile,
        )
        with pytest.raises(PermissionError, match="aegis_ingestor"):
            await KnowledgeEngine(unsafe_ingestor_store).ingest(
                KnowledgeDocument(
                    tenant_id=str(tenant_a),
                    document_id="wrong-role-write",
                    title="Must not be written by a privileged role",
                    source="security-baseline",
                    content="Role validation prevents accidental superuser use.",
                    classification=KnowledgeClassification.PUBLIC,
                )
            )

        rollback_profile = EmbeddingSpaceProfile(
            provider="test-provider",
            model="test-embedding",
            model_revision="rollback-revision",
            dimensions=3,
        )
        rollback_store = PostgresKnowledgeStore(
            runtime_session_factory=runtime_factory,
            ingestor_session_factory=ingestor_factory,
            subject=actor_a,
            tenant_id=tenant_a,
            embeddings=embeddings,
            embedding_space=rollback_profile,
        )
        oversized_source = "https://security.example/" + ("a" * 2050)
        with pytest.raises(DBAPIError):
            await KnowledgeEngine(rollback_store).ingest(
                KnowledgeDocument(
                    tenant_id=str(tenant_a),
                    document_id="rollback-document",
                    title="Transaction rollback test",
                    source="security-baseline",
                    content="The document insert violates the database source URI bound.",
                    source_uri=oversized_source,
                    classification=KnowledgeClassification.PUBLIC,
                )
            )

        async with admin_factory() as session:
            counts = (
                await session.execute(
                    text("""
                        SELECT
                            (SELECT count(*) FROM public.knowledge_documents
                             WHERE tenant_id = :tenant_id AND document_key = 'baseline-a'),
                            (SELECT count(*) FROM public.knowledge_chunks chunk
                             JOIN public.knowledge_documents document
                               ON document.tenant_id = chunk.tenant_id
                              AND document.id = chunk.document_id
                             WHERE chunk.tenant_id = :tenant_id
                               AND document.document_key = 'baseline-a'),
                            (SELECT count(*) FROM public.knowledge_documents
                             WHERE tenant_id = :tenant_id
                               AND document_key = 'wrong-role-write'),
                            (SELECT count(*) FROM public.knowledge_embedding_spaces
                             WHERE tenant_id = :tenant_id
                               AND model_revision = 'rollback-revision'),
                            (SELECT count(*) FROM public.knowledge_documents
                             WHERE tenant_id = :tenant_id
                               AND document_key = 'rollback-document')
                    """),
                    {"tenant_id": tenant_a},
                )
            ).one()
            assert counts[0] == 1
            assert counts[1] == first_count
            assert counts[2] == 0
            assert counts[3] == 0
            assert counts[4] == 0
    finally:
        await ingestor_engine.dispose()
        await provisioner_engine.dispose()
        await runtime_engine.dispose()
        await admin_engine.dispose()
