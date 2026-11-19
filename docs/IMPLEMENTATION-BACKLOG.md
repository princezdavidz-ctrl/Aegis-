# AEGIS implementation backlog

**Repository:** `princezdavidz-ctrl/Aegis-`  
**Baseline:** `main` at `a36b197f711be384b9b8cb54c7361a83db5074ce`  
**Planning date:** 2026-11-14

This backlog is based on an inspection of the current `main` branch. It separates implemented foundations from live, externally configured capabilities. A feature is not considered operational merely because a UI screen, interface, schema or deployment workflow exists.

## Current repository assessment

| Area | Current state | Remaining proof or work |
|---|---|---|
| React portal | Responsive shell, Organization profile, Asset Inventory and Members screens with typed tenant API clients and regression tests exist; React session provider wires the provider-neutral OIDC Authorization Code + PKCE adapter, handles callback, and exposes sign-in/local sign-out | No non-production IdP/client/redirect/API audience is configured, so sign-in remains disabled; server-verified membership bootstrap is still required before customer data pages can receive a session; organization profile editing and browser-driven authenticated tests remain pending |
| FastAPI | App factory, OIDC verifier, tenant/profile/membership/manual asset APIs, endpoint enrollment/fleet APIs and advisory AI analysis route exist | Live IdP/database configuration, non-production identity verification and production deployment proof |
| Tenant security | Membership resolution, tenant context and PostgreSQL RLS migration exist | Run migrations against PostgreSQL and prove RLS under production-like roles |
| Audit | Append-only audit model/sink and database migration protections exist | Verify durable writes and database immutability on PostgreSQL |
| AI | Provider-neutral gateway, OpenAI-compatible adapter, four advisory specialist workflows, deterministic evaluation, embeddings adapter and tenant-scoped pgvector schema exist | PostgreSQL KnowledgeStore adapter, live provider config, tenant evidence retrieval, retrieval evaluation and operational governance |
| Flutter desktop | Engineer SOC shell and module navigation exist | Real API data, authentication, analyst workflows and realtime updates |
| AWS | OIDC-based manual deployment workflow and role Terraform foundation exist | Provision AWS resources, correct/configure OIDC provider, set repository variables and execute staging deployment |
| Telemetry/detection | Architecture and module placeholders exist | Connectors, event pipeline, detection rules and correlation are not operational |
| Response | Security policy and patch/response planning boundaries exist | Approval, execution, verification and rollback workflows are not implemented |

## Delivery rules

1. Work from the latest `main`; inspect current code before each increment.
2. Prefer small vertical slices with tests over broad placeholder scaffolding.
3. Do not duplicate existing OIDC, tenant, RLS, audit or AI gateway foundations.
4. Every tenant-owned resource, job, cache key, report and evidence retrieval path must be tenant-scoped.
5. AI remains advisory. Consequential actions require deterministic policy checks and human approval.
6. Customer connectors are read-only by default and require explicit, scoped authorization.
7. Never commit credentials or use long-lived AWS access keys. Use GitHub OIDC for AWS deployment.
8. A phase is complete only when its acceptance criteria, CI and required integration evidence pass.
9. Merge completed changes into `main` after successful checks; record the merge SHA and update this backlog.
10. Do not claim a live integration, deployment, 24/7 human response or compliance certification without evidence.

## Phase map and GitHub work items

| Phase | Objective | Dependency | GitHub issue |
|---|---|---|---|
| 1 | Secure foundation and staging readiness | Existing foundation; AWS admin and IdP setup | [#17](https://github.com/princezdavidz-ctrl/Aegis-/issues/17) |
| 2 | Tenant onboarding, organizations, users and assets | Phase 1 | [#18](https://github.com/princezdavidz-ctrl/Aegis-/issues/18) |
| 3 | Authorized connectors and telemetry ingestion | Phases 1–2 | [#19](https://github.com/princezdavidz-ctrl/Aegis-/issues/19) |
| 4 | Deterministic detection and correlation | Phase 3 | [#20](https://github.com/princezdavidz-ctrl/Aegis-/issues/20) |
| 5 | Evidence-grounded AI agents | Phases 1–4 | [#21](https://github.com/princezdavidz-ctrl/Aegis-/issues/21) |
| 6 | SOC desktop and incident operations | Phases 1, 2, 4, 5 | [#22](https://github.com/princezdavidz-ctrl/Aegis-/issues/22) |
| 7 | Human-approved response and remediation | Phases 1, 3–6 | [#23](https://github.com/princezdavidz-ctrl/Aegis-/issues/23) |
| 8 | Customer portal, reporting and compliance evidence | Phases 1–4, 6 | [#24](https://github.com/princezdavidz-ctrl/Aegis-/issues/24) |
| 9 | Production hardening and controlled pilot | Phases 1–8 | [#25](https://github.com/princezdavidz-ctrl/Aegis-/issues/25) |
| 10 | Scale and advanced threat intelligence | Phase 9 and validated demand | [#26](https://github.com/princezdavidz-ctrl/Aegis-/issues/26) |

## Phase 1 execution order

Phase 1 code-level security foundations are merged and covered by CI. Live staging readiness remains an external prerequisite; Phase 2 customer workflows are the active application-development priority. Complete the remaining Phase 1 staging tasks when the required account and identity-provider configuration is available:

1. Reconcile README and deployment documentation with the current API implementation.
2. Verify Alembic migrations against a disposable PostgreSQL database.
3. Add PostgreSQL RLS and audit immutability integration tests.
4. Verify the OIDC verifier with a real test IdP configuration in a non-production environment.
5. Reconcile Docker health check and ALB health path; add image build/smoke CI.
6. Correct the GitHub OIDC Terraform provider implementation/documentation mismatch.
7. Add dependency, secret and static security scanning.
8. Complete staging infrastructure and deployment smoke test once an AWS administrator provisions resources.
9. Record exact external configuration still outstanding; do not mark deployment complete prematurely.

## Phase exit evidence

For every phase, attach:
- merged PR and merge commit;
- CI run URLs and test counts;
- migration/integration evidence where relevant;
- security and tenant-isolation test results;
- updated documentation and operational runbook;
- unresolved external prerequisites and accepted risks.

## Explicit non-goals for early releases

- No autonomous production remediation.
- No arbitrary shell execution or unrestricted security-tool execution by AI.
- No cross-tenant model context or customer-data training by default.
- No claim that the platform is monitoring continuously until ingestion, alerting and staffing are operational.
- No production AWS deployment until the exposed AWS access key incident is confirmed remediated and the account is configured for OIDC-only deployment.


## Completed vertical slice — server-verified membership bootstrap

Implement the identity-to-tenant handoff before connecting customer pages to live data.

### API contract

- Add a read-only authenticated endpoint that derives the subject only from the verified bearer-token principal.
- Return only active memberships belonging to that exact subject, with the tenant slug, display name and server-resolved role needed by the portal.
- Do not accept tenant UUIDs, subject IDs or role values from the browser. Do not infer membership or role from ID-token claims.
- Preserve database row-level security and least-privilege runtime grants. If a cross-tenant membership lookup needs a database function or separate query boundary, give it a narrowly scoped contract and prove it cannot enumerate another user's memberships.
- Keep the endpoint free of mutations and append-only audit writes unless the reviewed security model requires them.

### Frontend contract

- Add a typed client that sends the short-lived access token with no cookie credentials, redirects or token persistence.
- Validate the complete response shape and reject duplicate or malformed membership entries.
- Allow the user to select only a tenant slug returned by the API. Keep the tenant UUID and role server-derived.
- Pass the selected slug and server-resolved role to the existing Organization, Assets and Members pages; the backend remains authoritative for every protected operation.

### Acceptance tests

- A verified subject receives only their own active memberships.
- Suspended, revoked and pending memberships are not selectable.
- A user cannot enumerate another subject's memberships or inject a tenant UUID/role.
- Empty membership lists, malformed responses, expired tokens and API failures leave customer pages locked.
- Existing tenant-isolation, PostgreSQL RLS, API-client and signed-out UI tests remain green.


### Completion record — 2026-11-15

- Added authenticated `GET /api/v1/me/tenants`; the subject is derived exclusively from the verified bearer principal.
- The API applies transaction-local PostgreSQL RLS subject context and returns only active memberships for that subject.
- The response contains only tenant slug, display name and server-resolved role; tenant UUIDs, membership IDs and identity subjects are not exposed.
- Added bounded, typed API contracts and fail-closed behavior when authentication or the membership store is unavailable.
- Added a strict frontend client with HTTPS/loopback-only origin validation, no cookies/redirects/cache, bounded token handling, duplicate-slug rejection and exact response-field validation.
- The React OIDC provider loads memberships after sign-in, clears stale membership state across session changes, and permits selection only from the server-returned membership list.
- Organization, Assets and Members receive a tenant session only after bootstrap succeeds. Existing APIs continue to resolve tenant IDs and roles server-side on every request.
- Added backend isolation/active-status/authentication/store-unavailable tests and frontend transport/schema tests.
- Merged PR #58 as `fa0a1a09fa69d2dcdc6daa01f533a56aac6993a7`; all PR and post-merge workflows passed. See the 2026-11-15 progress entry for detailed test counts and run links.

## Completed vertical slice — deterministic AI evaluation framework (PR #43)

- Added immutable evaluation case/report contracts, `evaluate_output`, and the public `evaluate_suite` helper under `services/ai/src/aegis_ai/evaluation/`.
- Added a versioned seed dataset and documented deterministic checks for evidence provenance, required/forbidden phrases, uncertainty and advisory-only language.
- This evaluator is an offline regression gate. It makes no model/network calls and does not establish real-world model accuracy or replace analyst review.
- Fixed the missing public export and Ruff's `UP035` import finding.
- Merged PR #43 as `ba293965d4fc8690b9d2af3cc08562bbebd79e17`.
- Validation: AI service **33 tests passed**, Ruff passed, and AEGIS, security, AI-service and Flutter post-merge workflows all passed. See `docs/PROGRESS.md` for exact run links.

## Completed vertical slice — configurable embeddings provider (PR #59)

- Ported the existing provider work onto the current main baseline instead of merging the stale PR #41 branch.
- Added the EmbeddingProvider protocol and OpenAI-compatible adapter with runtime-only credentials.
- Enforced HTTPS for remote endpoints, exact loopback-only HTTP for development, bounded batches/text, response ordering and strict vector/index validation.
- Rejected zero/non-finite vectors and non-numeric/boolean values; sanitized transport and provider errors; disabled redirects.
- Added mocked HTTP tests; no live provider or API key is required.
- PR #59 final tested head: b2511a3c40259f7b86286933da416ff30722e606.
- Merged into main as 60cecb3e4b77d9335af52b745ae6003325048c99; all post-merge AEGIS, security, AI service and Flutter workflows passed.
- Validation: AI service 56 tests passed, Ruff passed, and AEGIS, security and Flutter workflows all passed. See docs/PROGRESS.md for run links and details.
- This is an adapter foundation only. It does not persist vectors, automatically ingest customer data, or enable semantic retrieval. The in-memory store remains development/test-only.

## Completed vertical slice — tenant-scoped pgvector schema (PR #60 merged)

- Added migration `0010_tenant_knowledge_store` for tenant-owned embedding spaces, documents and chunks.
- Every knowledge table uses forced RLS. Reads and ingestion writes require transaction-local tenant context plus an active membership for the verified subject.
- Composite foreign keys prevent chunks from referencing another tenant's document or embedding space.
- Embedding spaces record provider, model, model revision and dimensions; chunk constraints verify the vector's actual dimensions and prevent incompatible spaces from being joined.
- Added generated lexical search vectors and a GIN index for the planned hybrid retrieval path.
- Embedding-space rows are write-once for the ingestor; model/revision/dimension changes create a new space. Document/chunk writes append audit events through a restricted SECURITY DEFINER trigger; the ingestor cannot insert audit rows directly or DELETE knowledge rows.
- PostgreSQL CI uses a pgvector-enabled PostgreSQL 16 image and enables the extension as the database administrator before applying migrations.
- The schema is a foundation only. No PostgreSQL KnowledgeStore adapter, customer ingestion or semantic retrieval is active.

## Next vertical slice — PostgreSQL KnowledgeStore adapter

1. Implement a backend-owned adapter behind the existing `KnowledgeStore` protocol, using the API's SQLAlchemy session boundary rather than adding a second database stack to the AI package.
2. Separate read-only runtime sessions from the RLS-bound ingestor session; set tenant and subject context transaction-locally for every operation.
3. Persist documents/chunks idempotently and keep document metadata, chunks and embeddings in one transaction so audit-trigger failures roll back the entire ingestion.
4. Embed document chunks and retrieval queries using one explicit provider/model/revision/dimension profile. Reject mismatched dimensions and never compare vectors across embedding spaces.
5. Implement exact vector similarity and lexical retrieval with tenant ID and embedding-space ID filters in SQL before ranking. Keep top-k bounded, add deterministic tie-breaking and preserve source/classification provenance.
6. Add PostgreSQL integration tests for repeat ingestion, updates, empty results, model-space mismatch, cross-tenant search denial and failure rollback. Do not fetch global candidates and filter them in application memory.
7. Wire the adapter into specialist augmentation only after the persistence and tenant-isolation tests pass. Retrieved content remains untrusted evidence.
8. Keep customer ingestion disabled until approved source authorization, retention and classification controls are connected.

The pgvector extension must be enabled by a database administrator before migration 0010. The current CI evidence validates the schema and RLS against a disposable PostgreSQL instance only; no live Neon database is configured or claimed.

Other open work remains separate: PR #37's integration-authorization migration has an outstanding PostgreSQL migration failure caused by SQLAlchemy interpreting a colon-prefixed token inside a SQL function body as a bind parameter; do not merge it until its migration/RLS checks pass.

 
### PR #60 validation status — 2026-11-18

- Migration repair commit: 22829a5a2ccb14cbe3ae0b70c349853f8769d9e6.
- The hosted AEGIS checks push run passed all eight jobs, including migration 0010 and the PostgreSQL knowledge/RLS integration test: [run #44298712784](https://github.com/princezdavidz-ctrl/Aegis-/actions/runs/44298712784).
- AI service, NVD catalogue and Flutter workflows passed.
- The security workflow remains blocked only by the newly reviewed, unpatched GHSA-fc5q-39xc-vjpf finding in transitive picomatch 4.0.7. Do not suppress the advisory, force an unverified package version or merge PR #60 while the required security workflow is red. Reassess when upstream publishes a fixed version or the repository owner explicitly accepts the documented build-time risk.
- The schema is validated against disposable pgvector PostgreSQL in CI only; no live Neon database is configured.

**Immediate next action:** resolve the npm advisory through a verified upstream release or explicit risk acceptance, then merge PR #60. After merge, implement the backend-owned PostgreSQL KnowledgeStore adapter described above.


### Merge and dependency-audit revalidation — 2026-11-19

- PR #60 was merged into `main` as squash commit `64325ebf210fe4f129d72050b9f65102a7f135a8` after all PR workflows passed.
- The previously failing security dependency-audit job was re-run after GitHub withdrew GHSA-fc5q-39xc-vjpf on 2026-11-18; the rerun passed, including npm audit. The advisory withdrawal is not a package patch, and picomatch 4.0.7 remains in the lockfile through development tooling. Continue monitoring; do not add an override or suppression without new evidence.
- PR validation evidence: AEGIS checks [#44299199105](https://github.com/princezdavidz-ctrl/Aegis-/actions/runs/44299199105), AI service [#44299199003](https://github.com/princezdavidz-ctrl/Aegis-/actions/runs/44299199003), Flutter [#44299199083](https://github.com/princezdavidz-ctrl/Aegis-/actions/runs/44299199083), NVD [#44299199102](https://github.com/princezdavidz-ctrl/Aegis-/actions/runs/44299199102), and security [#44299198857](https://github.com/princezdavidz-ctrl/Aegis-/actions/runs/44299198857).
- The schema remains validated against disposable pgvector PostgreSQL only. No live Neon database or production ingestion is configured.

**Next implementation:** build the backend-owned PostgreSQL KnowledgeStore adapter behind the existing AI protocol. Use separate read-only runtime and RLS-bound ingestor session factories, transaction-local verified subject/tenant context, explicit embedding-space identity, SQL-scoped vector and lexical retrieval, bounded top-k, provenance, and atomic audited persistence. Add PostgreSQL tests for idempotency, version conflicts, tenant isolation, classification filtering and rollback before wiring retrieval into specialist augmentation.
