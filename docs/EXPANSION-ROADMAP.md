# AEGIS Expansion Roadmap — Phases 11–20

**Status:** Approved for staged implementation  
**Baseline:** `main` at `50b9ab766895b1b35dd595e2a51d5e8526f7bddc`  
**Rule:** These phases extend the existing platform roadmap; they do not replace or bypass its identity, tenancy, audit, AI-governance or production-readiness gates.

## Product outcome

Extend AEGIS into a unified, multi-tenant cybersecurity platform covering endpoint visibility, authorized security assessment, network detection, SIEM, cloud posture, application security, identity threat detection, governed response, compliance evidence and advanced AI SOC orchestration.

## Non-negotiable engineering controls

- Every customer asset, event, scan, finding, connector, job, report and approval is tenant-scoped from authenticated server-side membership. Never accept tenant ownership from an agent or browser payload.
- Integrations are read-only by default. Every connector has explicit customer authorization, narrowly scoped credentials, expiry/revocation, health reporting and an auditable data boundary.
- Endpoint agents are signed, least-privilege, tamper-evident and updateable. They collect only documented telemetry; no covert surveillance, credential harvesting or arbitrary remote shell.
- Pentesting is limited to verified customer-owned or explicitly authorized targets, written scope, approved windows, rate limits, safe checks and emergency stop. No uncontrolled exploitation, persistence, destructive testing, denial-of-service or stealth.
- Network monitoring respects customer-approved interfaces, retention and privacy boundaries.
- AI treats telemetry, source code, logs, tickets and tool output as untrusted data. AI is advisory; deterministic policy gates and human approvals govern consequential actions.
- No production patch, endpoint isolation, account disablement, firewall change or other disruptive action without explicit approval, precondition checks, payload binding, expiry, verification and rollback.
- No cross-tenant retrieval, event routing, caches, model context or reporting. No shared model training on customer data by default.
- A module is not "complete" until implementation, tests, CI, documentation and relevant integration evidence exist. UI placeholders and schemas alone do not count.

## Phase 11 — Endpoint agent and operating-system integrations

**Scope**
- Lightweight endpoint collector for Windows, Linux and macOS.
- OS-specific adapters for Windows Event Log/Sysmon and Defender signals; Linux journald/auditd/package inventory; macOS unified logs, FileVault and security posture.
- Device enrollment, key rotation, signed updates, heartbeat, health and revocation.
- Inventory of processes, services, packages, configuration posture and file-integrity events, with explicit collection policy.
- Backend ingestion contract, tenant-bound asset association, event normalization and endpoint health in portal/desktop.

**Implementation sequence**
1. Define signed agent identity/enrollment and device lifecycle.
2. Define versioned, privacy-reviewed telemetry schema and collection profiles.
3. Implement Windows/Linux/macOS collectors independently behind a shared agent core.
4. Add authenticated ingestion, replay protection, deduplication and tenant isolation.
5. Add agent fleet UI, health, upgrade and revocation workflows.

**Acceptance**
- Agent cannot enroll to or submit data for another tenant.
- Invalid signatures, expired/revoked credentials, replayed events and oversized payloads are rejected.
- Collection is visible, configurable and bounded; uninstall/revocation stops ingestion.
- OS-specific tests run in CI; native integration tests run on matching runners.

## Phase 12 — Authorized penetration-testing engine

**Scope**
- Engagement lifecycle: customer authorization, verified asset ownership, explicit targets, exclusions, testing window, allowed test profiles, rate limits and emergency stop.
- Safe reconnaissance and configuration checks; network and web/API assessment adapters.
- Findings with evidence, reproducibility, severity, confidence, CVE/CWE/CVSS/EPSS references and remediation guidance.
- Attack-path visualization from validated findings; controlled retesting and signed reports.

**Safety boundary**
- Start with passive and non-destructive checks. Active checks require a separately approved engagement and explicit target allowlist.
- No denial-of-service, destructive payloads, persistence, stealth, credential theft, malware deployment or testing third-party targets.
- Exploit validation uses harmless proof checks or isolated customer-approved test environments; human approval is required before intrusive validation.

**Acceptance**
- Scope is enforced in the scheduler and again by each execution adapter.
- Out-of-scope targets, expired engagements, disallowed test types and rate-limit breaches are blocked and audited.
- Every test is attributable to an approved engagement and can be stopped immediately.
- Reports distinguish confirmed findings from inferred risk.

## Phase 13 — Network detection and response

**Scope**
- Integrations for Suricata, Zeek, DNS, firewall and network-flow telemetry.
- Network asset mapping, protocol metadata, IDS alerts, suspicious beaconing and lateral-movement analytics.
- Connector health, sensor coverage, event freshness and data-loss visibility.

**Acceptance**
- Sensor identity and network scope are authorized and tenant-bound.
- Event normalization preserves source provenance and timestamps.
- Detection tests use benign replay datasets and document false-positive behavior.
- No inline blocking or network reconfiguration in this phase.

## Phase 14 — SIEM and event correlation

**Scope**
- Versioned normalized event model and mapping for OCSF/ECS-compatible sources where practical.
- Durable ingestion pipeline with queueing, back-pressure, deduplication, retries, dead-letter handling and replay.
- Search, filtering, retention controls, correlation rules, case linking and event provenance.
- Detection content lifecycle: versioning, testing, staged rollout, suppression and rollback.

**Acceptance**
- Tenant separation is tested across ingestion, storage, search, queue, cache and exports.
- Ingestion throughput, lag, loss and retention are measurable.
- Rule changes are reviewed, tested against replay datasets and auditable.

## Phase 15 — Cloud security posture and workload integrations

**Scope**
- AWS, Azure and Google Cloud inventory and posture connectors.
- Least-privilege read-only cloud roles, resource discovery, configuration findings, IAM exposure and storage/network posture.
- Container registry and Kubernetes posture integrations.

**Acceptance**
- Customer grants scoped read-only access with explicit revocation and credential rotation.
- Connector cannot access resources outside granted account/subscription/project.
- Findings retain cloud resource identifiers, source evidence and collection time.
- Remediation remains recommendation-only until Phase 18 controls are satisfied.

## Phase 16 — Application, API and software supply-chain security

**Scope**
- SAST, DAST safe profiles, SCA, secret scanning, IaC scanning, container scanning and SBOM ingestion.
- GitHub/GitLab/Bitbucket and CI/CD integrations.
- API inventory, authentication/authorization checks, dependency and build provenance findings.
- Developer-facing findings, fix proposals and regression verification.

**Acceptance**
- Repository and pipeline permissions are narrowly scoped and revocable.
- Secret values are redacted before storage/model context.
- DAST requires an authorized target and safe test profile.
- Code changes are proposed as diffs and require repository-owner review.

## Phase 17 — Identity threat detection

**Scope**
- Entra ID, Active Directory and supported identity provider signals.
- Risky sign-ins, MFA posture, privileged role changes, dormant accounts, token/session anomalies and excessive permissions.
- Identity-to-asset and identity-to-incident relationships.

**Acceptance**
- Read-only access by default; no password collection.
- Identity data is minimized and retention-controlled.
- Detection outputs cite source events and distinguish risk indicators from confirmed compromise.
- Account disablement/session revocation is deferred to governed response.

## Phase 18 — Human-approved response and security automation

**Scope**
- Typed action catalog and policy engine for supported containment/remediation actions.
- Approval inbox, separation of duties, customer/engineer authority, expiry and exact payload/target binding.
- Short-lived credentials, idempotency, precondition checks, execution journal, postcondition verification and rollback.
- Playbook simulation and dry-run mode.

**Acceptance**
- Deny by default; no AI-only approval or execution.
- Approval becomes invalid if action, target, parameters or evidence change.
- Expired, replayed, cross-tenant or unauthorized actions are denied.
- Every action has proposal, policy decision, approval, execution, verification and rollback evidence.
- Production execution is disabled until the integration-specific safety case passes.

## Phase 19 — Compliance, risk and evidence management

**Scope**
- Control mappings for selected frameworks (e.g. CIS Controls, NIST CSF, ISO 27001 and SOC 2 evidence mapping).
- Evidence collection, control owners, exceptions, risk register, remediation tracking and export.
- Customer-specific policy profiles and audit-ready reports.

**Acceptance**
- Evidence is traceable to source, owner, collection time and scope.
- Missing evidence is shown as unknown/not assessed, never silently compliant.
- AEGIS reports evidence mappings; it does not claim certification or legal compliance.

## Phase 20 — Advanced AI SOC orchestration

**Scope**
- Multi-agent orchestration for triage, threat hunting, correlation, investigation and reporting.
- Evidence-grounded retrieval with tenant-bound access checks, source citations and confidence/limitations.
- Model routing, budgets, redaction, evaluation, fallbacks and human handoff.
- Agent task plans with typed tools and policy-checked permissions.

**Acceptance**
- Agents cannot expand their own permissions or bypass policy gates.
- Every factual finding links to tenant-authorized evidence.
- Prompt-injection, data-exfiltration, cross-tenant and unsafe-action evaluations pass.
- Model/provider outage degrades safely; AI is never the sole control for consequential actions.

## Cross-phase platform work

These are shared enablers, not standalone feature claims:
- Tenant-safe event bus, object storage and search architecture for high-volume telemetry.
- Connector SDK with common auth, scopes, health, revocation, retries and audit.
- Secrets management and short-lived workload identities.
- Data classification, retention, deletion, export and regional residency controls.
- Observability, SLOs, incident response, backup/restore and cost guardrails.
- Desktop and portal route/navigation integration only as backend capabilities become real.

## Delivery cadence and merge policy

Each phase is delivered as multiple small vertical increments. For every increment:
1. Inspect current `main` and reuse existing domain/security foundations.
2. Implement a working backend contract or service before presenting a UI as operational.
3. Add unit, API, tenant-isolation, abuse-case and integration tests appropriate to the change.
4. Update module documentation, configuration examples and operational guidance.
5. Open a PR to `main`; wait for all required checks and fix failures.
6. Merge with the expected head SHA only after checks pass; record merge SHA and evidence.
7. Update `docs/PROGRESS.md` and this roadmap with honest implemented/verified/blocked status.

## First implementation slices

1. **Phase 11A:** endpoint agent protocol, device enrollment threat model, event envelope and schema validation.
2. **Phase 11B:** server-side enrollment/revocation and tenant-bound device identity.
3. **Phase 11C:** Linux collector MVP and signed packaging; then Windows and macOS collectors.
4. **Phase 12A:** pentest engagement authorization/scope model and policy tests before any scanner execution.
5. **Phase 13A–20A:** define contracts and safe vertical slices after their dependencies are established.

The sequence deliberately builds endpoint trust and data boundaries before active assessment or response automation.
