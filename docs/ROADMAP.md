# AEGIS Implementation Roadmap

**Product decisions locked:** all industries and organization sizes; continuous monitoring; human approval for consequential actions; multiple interchangeable AI model providers; full platform scope delivered in phases.

## Delivery principles

- Build the whole product architecture in sequence; do not attempt to ship every capability at once.
- Ship a usable engineer console early because the human SOC is central to the approval-first operating model.
- Every phase ends with working code, automated tests, documentation and a demonstrable acceptance result.
- No production write action before tenant isolation, authorization, audit, approval, verification and rollback controls are in place.
- Keep model and security-tool providers replaceable.
- Mark features as implemented only after tests and deployment evidence exist.

## Phase 0 — Product and engineering baseline

**Deliverables**
- Architecture, security model, domain boundaries and this roadmap.
- Repository conventions, branch/PR policy, issue templates and definition of done.
- Threat model and initial data classification.

**Exit criteria**
- Architecture decisions reviewed; risks and assumptions recorded.
- CI plan and implementation tickets agreed.

## Phase 1 — Secure application foundation

**Deliverables**
- Monorepo structure and React/TypeScript/Tailwind web application.
- FastAPI service with health/readiness endpoints, typed configuration and structured errors.
- Neon Postgres migrations and local development setup.
- Authentication integration, MFA-ready privileged access, RBAC and tenant context.
- Audit-event foundation, request IDs, secrets/configuration patterns.
- CI for formatting, linting, type checks, unit tests, dependency and secret scanning.

**Exit criteria**
- Customer and workforce identities can sign in through supported flows.
- Tenant-owned test records cannot be read or modified across tenant boundaries.
- Clean install, migration, test and build run reproducibly in CI.
- No credentials committed; health and deployment smoke tests work.

## Phase 2 — Tenant onboarding and customer portal

**Deliverables**
- Organization registration/invitation and onboarding workflow.
- Tenant profile, industry, organization size, region, data-retention preferences and policy profile.
- Membership management and customer roles.
- Asset inventory and connector authorization wizard.
- Customer overview with onboarding status, asset coverage and initial security posture.
- Subscription/plan entitlements designed without hard-coding industry assumptions.

**Exit criteria**
- A company can onboard, invite users, register assets and revoke a connector.
- Every object and API is tenant-scoped and covered by isolation tests.
- Onboarding and integration authorization events are audited.

## Phase 3 — Engineer SOC console and service operations

**Deliverables**
- Workforce identity and roles: Security Engineer, Senior Engineer, SOC Manager, Platform Admin.
- Tenant assignment and case ownership.
- Unified alert/incident queue with severity, status, SLA clock and filters.
- Incident workspace: evidence, timeline, notes, tasks, escalation and customer communication.
- Approval inbox and immutable action history.
- Shift handover, escalation policies and operational runbooks.

**Exit criteria**
- Engineers see only authorized assigned tenants/cases; privileged access is audited.
- A case can be assigned, investigated, escalated and closed with evidence.
- Customer and engineer views show consistent case state.

## Phase 4 — Continuous telemetry and integrations

**Deliverables**
- Versioned event schema and connector framework.
- Initial read-only integrations selected by customer demand (recommended first set: cloud inventory/log sources, GitHub, endpoint telemetry and vulnerability scanner).
- Queue-backed ingestion, normalization, deduplication, retries and dead-letter handling.
- Connector health, event freshness, source coverage and ingestion lag dashboards.
- Detection rules and alert lifecycle.

**Exit criteria**
- Authorized test sources stream events continuously in a staging environment.
- Back-pressure, duplicate delivery, outage recovery and connector revocation are tested.
- Detection evidence links to source events and affected assets.

## Phase 5 — AI gateway and investigation agents

**Deliverables**
- Multi-provider model gateway with task routing, versioning, usage limits, fallback and redaction controls.
- Orchestrator and agent-run lifecycle.
- Asset enrichment, vulnerability triage, alert enrichment, threat-intelligence context and incident-investigation agents.
- Structured outputs with evidence references, confidence, limitations and trace IDs.
- Offline evaluation datasets, safety tests and prompt-injection defenses.

**Exit criteria**
- Provider can be changed without rewriting domain logic.
- Agents cannot access another tenant or call tools outside granted scope.
- Evaluation measures factual grounding, false positives, latency, cost and unsafe recommendations.
- AI outputs are clearly labeled as recommendations, not verified facts.

## Phase 6 — Detection, correlation and 24/7 response operations

**Deliverables**
- Cross-source correlation and prioritized cases.
- Severity model, suppression/tuning workflow and analyst feedback loop.
- Notification and escalation channels.
- Source health monitoring and alert-pipeline SLO dashboards.
- On-call rota, severity playbooks, shift handover and customer communication templates.

**Exit criteria**
- End-to-end detection-to-SOC workflow is tested with simulated defensive scenarios.
- Missed/delayed telemetry and notification failures are observable and alerted.
- Service tiers state coverage hours and response targets; 24/7 monitoring is not misrepresented as guaranteed human response without staffing.

## Phase 7 — Human-approved response and AI patch assistant

**Deliverables**
- Typed response proposals and policy/approval engine.
- Customer and engineer approval paths, action expiry and payload binding.
- Read-only investigation playbooks and tightly scoped response adapters.
- Patch assistant for supported repositories/configuration: proposed diff, rationale, tests, dependency impact and rollback notes.
- Isolated test execution and code scanning before approval.
- Execution worker with short-lived credentials, precondition checks, verification and rollback support.

**Exit criteria**
- No consequential action executes without valid approval from the correct authority.
- Approval is invalidated if target or payload changes.
- Production deployment requires the required customer authorization and engineer approval.
- Every action has traceable proposal, approval, execution, verification and rollback records.
- Automated tests prove denial of unauthorized, expired, replayed and cross-tenant actions.

## Phase 8 — Reporting and compliance

**Deliverables**
- Customer dashboards and scheduled daily/weekly/monthly reports.
- Incident reports, risk trends, asset coverage and remediation aging.
- Configurable compliance/control mappings by customer profile.
- Evidence exports and report access audit.

**Exit criteria**
- Reports are derived from recorded data, cite evidence and disclose missing coverage.
- Customers can export their own data only.
- Compliance status is described as evidence mapping, not certification.

## Phase 9 — Production hardening and controlled launch

**Deliverables**
- Independent security review and penetration test.
- Load, resilience, failover, backup/restore and disaster-recovery exercises.
- Data retention/deletion workflows and customer offboarding.
- Operational dashboards, cost controls, incident response and support processes.
- Deployment environments, release approvals, rollback and change management.
- Pilot onboarding, feedback, runbooks and support documentation.

**Exit criteria**
- Critical/high findings from security review are resolved or formally risk-accepted.
- Recovery objectives are tested and documented.
- Tenant isolation, approval and audit controls pass security regression tests.
- Pilot customers have explicit scopes, contacts, escalation expectations and service terms.

## Phase 10 — Scale and advanced capabilities

**Potential deliverables**
- Dedicated tenant data planes for customers requiring stronger isolation.
- Additional cloud, endpoint, identity, network, SIEM and developer-platform integrations.
- Advanced threat hunting, behavioral analytics and cross-signal attack-path analysis.
- More compliance frameworks and regional data controls.
- Customer-configurable bounded automation, only after separate authorization and safety validation.

**Exit criteria**
- Scale and advanced features are supported by measured demand, capacity tests and documented risk review.

## First implementation sprint

Start with a thin but real vertical slice:

1. Add the monorepo skeleton, developer documentation and CI workflow.
2. Build the web app shell with separate customer and engineer route groups.
3. Build FastAPI health/readiness and configuration modules.
4. Add Neon migration tooling and tenant/user/role/audit base schema.
5. Implement authentication boundary and server-side tenant authorization.
6. Add tests for cross-tenant denial, role denial and audit event creation.
7. Deploy preview frontend and staging API only after CI passes.

**Do not start with autonomous remediation.** Establish identity, tenancy, auditability and a working engineer workflow first.
