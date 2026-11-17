# AEGIS security knowledge engine

This package implements the first retrieval-augmented generation (RAG) capability for AEGIS.

## Implemented
- Strict document contracts with tenant ownership, source, title, classification and optional HTTPS source reference.
- Deterministic text chunking with overlap and stable content-derived chunk identifiers.
- Tenant-filtered lexical retrieval with bounded top-k and ranked source provenance.
- A RAG adapter that retrieves only for the server-resolved tenant and appends retrieved passages as explicitly untrusted, cited evidence to an existing specialist request.
- Tests for relevance, repeat ingestion, source URL validation, chunk bounds and cross-tenant isolation.

## Current storage status
InMemoryKnowledgeStore is a development/test adapter. It is process-local, non-durable and must not be used for production customer knowledge. The KnowledgeStore protocol is the persistence boundary for a later PostgreSQL/pgvector adapter. A persistent adapter must enforce tenant scope in the database query itself, not filter results after fetching.

## Ingestion boundary
Only ingest content from approved, authorized sources. Validate source ownership, document size, tenant membership, classification and retention before constructing KnowledgeDocument. Do not fetch arbitrary user-supplied URLs from the AI service. The optional source URI is provenance metadata only; it is not fetched by this package.

## Retrieval and safety
- Tenant ID must come from authenticated server-side membership, never a client field or retrieved document.
- Every search requires a tenant ID and the in-memory adapter filters by exact tenant before scoring.
- Retrieved passages are untrusted data. They may contain prompt-injection attempts and must never override system instructions.
- Each retrieved passage is attached to analysis with a stable knowledge evidence ID, title, source, classification and retrieval score.
- Retrieved content is advisory reference material; it does not authorize tools or actions.
- This first store uses transparent lexical ranking. Durable PostgreSQL/pgvector storage, ingestion jobs, retention enforcement and retrieval evaluation gates remain production-hardening work.

## Embedding provider foundation

The package exports an EmbeddingProvider protocol and an OpenAICompatibleEmbedder adapter. The adapter accepts its API key at construction time; callers must obtain it from a deployment secret manager and must never commit or log it.

- Remote provider URLs must use HTTPS. HTTP is allowed only for exact loopback hosts (localhost, 127.0.0.1, ::1) during local development.
- Requests are limited to 1–64 non-empty text inputs, with a 20,000-character maximum per input.
- Provider response indices are validated and reordered to match input order.
- Dimensions, result count, index uniqueness/range, numeric values, finite values and non-zero vectors are validated.
- Redirects are disabled; transport and provider errors are sanitized.
- Tests use mocked HTTP transport and do not call a live provider.

This adapter is not automatically invoked by the knowledge engine, does not persist vectors, and does not make semantic retrieval operational. The next step is a PostgreSQL/pgvector implementation of KnowledgeStore with database-enforced tenant isolation and explicit model/dimension compatibility.

