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
| AI | Provider-neutral gateway, OpenAI-compatible adapter, four advisory specialist workflows and backend wiring exist | Live provider config, tenant evidence retrieval, evaluation and operational governance |
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

## Next vertical slice — finish configurable embeddings provider (PR #41)

Review and complete the existing [PR #41](https://github.com/princezdavidz-ctrl/Aegis-/pull/41) before implementing persistent retrieval.

1. Move `Sequence` to `collections.abc` to satisfy Ruff.
2. Replace the NaN self-comparison in the test fixture with an explicit finite/NaN assertion while retaining coverage of non-finite provider responses.
3. Review batch bounds, input length limits, HTTPS enforcement, response ordering, vector dimensions, zero/non-finite rejection and sanitized provider errors.
4. Keep tests on mocked HTTP transport; do not require a live provider or commit API credentials.
5. Run AI service pytest and Ruff, then all relevant repository security/build workflows before merging.
6. After the provider contract is merged, design PostgreSQL/pgvector persistence and hybrid retrieval with database-enforced tenant isolation.

Other open work remains separate: PR #37 has a PostgreSQL migration failure caused by SQLAlchemy interpreting a colon-prefixed token inside a SQL function body as a bind parameter; do not merge it until its migration/RLS checks pass.
