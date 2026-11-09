# AEGIS Security and Operations Model

## Purpose

This document defines the minimum security and operational rules for a multi-tenant cybersecurity service that continuously monitors customer-authorized environments and uses AI to assist human security engineers.

## Authorization and scope

- Each customer must approve a written service scope before connectors or active security operations are enabled.
- Record tenant, source/account, asset selectors, permitted collection, permitted tests, excluded systems, time window, contact and expiry.
- Read-only collection is the default. Active scanning, containment, configuration changes and deployment require separate explicit scope.
- Connector credentials are stored in a managed secret system, scoped to minimum permissions, rotated and revocable.
- A revoked or expired authorization stops future collection/action and invalidates pending actions for that scope.

## AI authority

AI is advisory by default. It may summarize evidence, correlate alerts, prioritize findings, propose investigations and prepare a patch or response plan. It must not independently execute consequential changes.

A consequential action includes production code/configuration changes, isolation of critical assets, disabling accounts or controls, credential rotation, deletion, destructive operations, or changes that could interrupt customer services.

Before execution:
1. Resolve actor, tenant, asset and exact operation.
2. Validate current customer authorization and policy.
3. Generate a typed action proposal with evidence, impact, prerequisites, test plan and rollback plan.
4. Obtain approval from an authorized AEGIS engineer and customer approver where required.
5. Bind approval to an immutable action payload and expiry.
6. Revalidate scope and policy immediately before execution.
7. Execute with short-lived least-privilege credentials.
8. Verify outcome, record evidence and roll back when safe and necessary.

Emergency automation is not part of the initial release. Any later exception requires explicit customer opt-in, narrowly bounded playbooks, hard limits, alerting, kill switch and audit.

## Tenant isolation

- Tenant identity is derived from authenticated server-side membership.
- Tenant ID from a request body, URL or header is never sufficient authorization.
- Tenant scope is applied to database access, queues, caches, search, object storage, agent context, reports and tool calls.
- Cross-tenant access tests are required for every tenant-owned resource and background job.
- Workforce support access is least-privileged, time-limited, purpose-bound and logged.
- Shared AI context or cross-customer learning is prohibited unless explicitly authorized under contract and privacy review.

## Data handling

Classify customer data at ingestion. Minimize collection and model context. Avoid placing secrets, credentials, personal data or unnecessary raw logs in prompts. Apply redaction and data-loss controls before sending content to external model providers. Configure retention and deletion by contract and applicable law. Do not use customer data for model training without explicit permission.

## Prompt and tool security

Treat logs, source code, tickets, documents, threat-intelligence feeds and tool output as untrusted data. Prompt injection inside customer-controlled content must not change system policy or grant new permissions.

- Use typed tool schemas and allowlisted operations.
- Enforce authorization in the tool adapter and again at execution.
- Restrict network egress and prevent arbitrary shell/URL execution.
- Separate analysis tools from write-capable tools.
- Record tool name, arguments (with secrets redacted), actor, tenant, result and policy decision.
- Validate AI-generated patches with tests, static analysis, dependency checks and isolated execution.

## Audit and evidence

Record authentication and authorization events, sensitive reads, tenant administration, connector changes, AI runs, model/provider selection, tool calls, approvals, execution, verification, export and deletion. Audit records should be append-only to ordinary application roles, time-synchronized and monitored for gaps. Keep references to large evidence objects rather than copying raw telemetry into audit rows.

## 24/7 operations

Continuous monitoring requires resilient ingestion and alerting, not merely a continuously running dashboard. Measure:
- Connector/source freshness and coverage.
- Queue lag, dropped events, retry and dead-letter rates.
- Detection latency and alert delivery.
- Worker, API, database and model gateway availability.
- SOC acknowledgement and response time by service tier.

Define on-call staffing, escalation contacts, response targets, customer communications and maintenance windows contractually. Do not advertise a human 24/7 response SLA unless the operational team and escalation coverage exist.

## Secure engineering baseline

- MFA for privileged roles and least-privilege service identities.
- Encryption in transit and at rest; managed secrets and key rotation.
- Dependency, secret, static-analysis and container scanning in CI.
- Code review and protected release process for production changes.
- Database migrations reviewed and reversible where practical.
- Backups, restore tests, disaster-recovery runbooks and incident exercises.
- Vulnerability intake, triage, remediation and disclosure process.

## Minimum release gates

A release that handles customer data must not proceed unless:
- Tenant-isolation and authorization tests pass.
- No unresolved critical secret or dependency exposure is present.
- Audit events exist for sensitive workflows.
- Connector scopes and revocation work.
- AI/tool execution cannot bypass policy or approval.
- Operational alerts exist for ingestion failure and audit pipeline failure.
- Backup and rollback procedures are documented for the changed components.
