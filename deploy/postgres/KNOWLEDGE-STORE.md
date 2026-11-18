# Tenant-scoped PostgreSQL knowledge store schema

Migration `0010_tenant_knowledge_store` creates the persistence boundary for
AEGIS knowledge documents, chunks and embedding-space metadata. It does not
install an ingestion API or activate semantic retrieval by itself.

## Prerequisite

A database administrator must enable pgvector before running Alembic:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The migration deliberately checks for the extension rather than attempting to
install it as `aegis_migrator`. The migration role is not a superuser. Neon
projects must have the `vector` extension enabled by an appropriately
privileged project/database administrator first.

## Tenant and embedding boundaries

- Every record carries a tenant UUID and is protected by forced PostgreSQL RLS.
- Read policies require both the transaction-local `aegis.tenant_id` and an
  active membership for `aegis.subject`.
- Composite foreign keys bind each chunk to a document and embedding space in
  the same tenant. A chunk cannot reference another tenant's document or
  embedding profile.
- Each embedding space records provider, model, model revision and dimensions.
  Chunks reference that exact space and store their dimension count; database
  constraints compare it with `vector_dims(embedding)`. Vectors from different
  model revisions or dimensions must never be compared.
- The vector column is dimension-flexible. Exact similarity queries must filter
  by both tenant and embedding-space ID. No approximate-nearest-neighbour index
  is created yet because a shared fixed dimension has not been selected. A
  future adapter may add a reviewed per-space/per-dimension index strategy.
- A generated `tsvector` and GIN index provide the lexical half of the planned
  hybrid retrieval path.

## Database roles

After migrations, run `deploy/postgres/grants.sql`:

- `aegis_runtime`: SELECT only on knowledge tables.
- `aegis_ingestor`: SELECT/INSERT/UPDATE on knowledge tables, with forced RLS
  requiring a matching active tenant membership and transaction-local context.
  It has no DELETE privilege.
- `aegis_ingestor` can read only its own membership row through the existing
  membership RLS policy so the knowledge policies can verify authorization.
- Inserts and updates to documents and chunks append audit events. If the audit
  insert fails, the knowledge write fails in the same transaction.
- `aegis_migrator`: schema ownership and migration-only policy.

The future adapter must set `aegis.subject` and `aegis.tenant_id` using
transaction-local settings on every connection/transaction. It must not accept
tenant scope from document content or model output.

## Current status

The schema, RLS policies, composite tenant constraints, embedding compatibility
checks and audit triggers are covered by PostgreSQL CI. The application-level
PostgreSQL KnowledgeStore adapter, ingestion orchestration, vector query path
and retention/deletion workflow are not implemented. The in-memory store
remains the only active KnowledgeStore adapter.

The downgrade drops AEGIS knowledge tables and triggers but intentionally
leaves the shared pgvector extension installed.
