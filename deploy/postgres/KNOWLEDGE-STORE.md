# Tenant-scoped PostgreSQL knowledge store schema

Migration `0010_tenant_knowledge_store` creates the persistence boundary for
AEGIS knowledge documents, chunks and embedding-space metadata. It does not
install an ingestion API or activate semantic retrieval by itself.

## Prerequisite

A database administrator must enable pgvector before running Alembic:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
GRANT USAGE ON TYPE public.vector TO aegis_migrator;
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
- `aegis_ingestor`: SELECT/INSERT on embedding spaces and SELECT/INSERT/UPDATE on documents/chunks, with forced RLS
  requiring a matching active tenant membership and transaction-local context.
  It cannot update embedding-space identity or DELETE any knowledge row. A model, revision or dimension change creates a new embedding space.
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
checks and audit triggers are covered by PostgreSQL CI. The backend-owned
`PostgresKnowledgeStore` adapter is implemented at
`backend/app/ai/knowledge_store.py` and covered by the same disposable
pgvector PostgreSQL CI service. It requires separate `aegis_runtime` and
`aegis_ingestor` session factories, checks `current_user` against the exact
least-privilege role before each operation, and applies transaction-local
subject/tenant context.

A fail-closed configuration contract is now defined in
`backend/app/ai/knowledge_config.py`. The optional settings are:

- `AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL` — `aegis_runtime` PostgreSQL role.
- `AEGIS_KNOWLEDGE_INGESTOR_DATABASE_URL` — `aegis_ingestor` PostgreSQL role.
- `AEGIS_KNOWLEDGE_EMBEDDING_PROVIDER` — provider identity label.
- `AEGIS_KNOWLEDGE_EMBEDDING_BASE_URL` — HTTPS embeddings endpoint; loopback
  HTTP is permitted only in development/test.
- `AEGIS_KNOWLEDGE_EMBEDDING_MODEL` and
  `AEGIS_KNOWLEDGE_EMBEDDING_REVISION` — explicit immutable model identity.
- `AEGIS_KNOWLEDGE_EMBEDDING_DIMENSIONS` — vector width (1–16000).
- `AEGIS_KNOWLEDGE_EMBEDDING_API_KEY` — secret-managed provider credential.
- `AEGIS_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS` — bounded request timeout (1–120).

No core settings means the feature remains disabled. Once any core setting is
supplied, the complete runtime/ingestor role pair and embedding profile are
required; partial configuration is rejected. Credentials are secret-wrapped
and excluded from representations.

This settings contract is not yet wired into the FastAPI lifecycle. The
in-memory store remains the active default and the PostgreSQL adapter is not
available to request handlers or specialist augmentation. Do not configure
customer ingestion or assume persistent memory is active until lifecycle
wiring, role checks and authorization tests are merged.

Document keys remain immutable for a content digest; changed source content
requires a new versioned document key until a reviewed soft-delete/retention
migration exists. Restricted documents remain excluded pending role-aware
classification authorization. No live Neon database or embedding provider is
configured.

The downgrade drops AEGIS knowledge tables and triggers but intentionally
leaves the shared pgvector extension installed.
