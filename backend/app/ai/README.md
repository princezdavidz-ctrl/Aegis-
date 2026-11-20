# Backend AI boundary

The FastAPI backend connects the provider-neutral specialist runtime when the
chat model settings are complete. Requests remain authenticated, tenant-scoped,
audited and advisory-only. The model provider is unconfigured by default; the
API fails closed rather than substituting a mock model.

## Persistent knowledge foundation

- `PostgresKnowledgeStore` implements the shared AI `KnowledgeStore` protocol
  in `knowledge_store.py`.
- The adapter uses separate `aegis_runtime` read-only and `aegis_ingestor`
  write-limited session factories, verifies `current_user`, and applies
  transaction-local subject/tenant RLS context for every operation.
- Vector and lexical retrieval is filtered by tenant and immutable embedding
  space before ranking. Restricted-classification content is excluded until
  role-aware authorization is implemented.
- `KnowledgeSettings` in `knowledge_config.py` defines the optional,
  fail-closed configuration contract. No memory settings means disabled;
  supplying any core setting requires the complete pair of database roles and
  embedding profile. Database URLs and the embedding API key are
  `SecretStr` values and are omitted from model representations.

The configuration contract is not yet loaded by the FastAPI lifespan, and the
Postgres adapter is not yet available to request handlers or specialist
augmentation. Do not configure customer ingestion or assume persistent memory
is active until lifecycle wiring and authorization tests are merged.

## Safety boundaries

Treat customer logs, source code, tickets, retrieved passages and tool output as
untrusted data. Retrieved text must never override system instructions or grant
permissions. Models remain advisory; deterministic policy and authorized human
approval control consequential actions. Prevent cross-tenant context,
retrieval, cache, memory and report leakage.

No model tool-calling surface, shell access, security-tool execution, patch
deployment or autonomous remediation is enabled by this subsystem.
