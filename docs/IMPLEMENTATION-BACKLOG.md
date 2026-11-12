# AEGIS implementation backlog

**Repository:** `princezdavidz-ctrl/Aegis-`  
**Baseline:** `main` at `75d375dcc1fa2cabca24c48a16c40183d7ab29f3`  
**Planning date:** 2026-11-12

This backlog is based on an inspection of the current `main` branch. It separates implemented foundations from live, externally configured capabilities. A feature is not considered operational merely because a UI screen, interface, schema or deployment workflow exists.

## Current repository assessment

| Area | Current state | Remaining proof or work |
|---|---|---|
| React portal | React/TypeScript shell and a read-only tenant asset inventory UI/client are present on the active development branch | Browser OIDC session adapter and live API connection are not configured; customer mutations remain disabled |
| FastAPI | App factory, health routes, optional OIDC verifier and advisory AI analysis route exist | Live IdP/database configuration, PostgreSQL integration proof and business APIs |
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

Phase 1 is the active priority. Execute in this order:

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


## 2026-11-12 customer portal increment

- The current `main` branch already contains the tenant-scoped asset inventory API and PostgreSQL isolation tests.
- Development branch `feat/customer-asset-inventory-ui` adds the corresponding read-only React page and a strict API client. It is not considered operational until the trusted browser OIDC session adapter and API origin are configured.
- The page uses the server-verified tenant membership flow; the browser supplies only the selected tenant slug and never supplies a tenant UUID.
- The next portal dependency is a verified browser OIDC session adapter. Asset mutations and member administration remain gated on session roles and existing backend authorization.
