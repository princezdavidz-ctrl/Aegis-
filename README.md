# AEGIS

**AI-assisted, human-governed cybersecurity operations for organizations of every size and industry.**

AEGIS is a multi-tenant managed security platform that continuously monitors customer-authorized environments, detects and investigates threats, coordinates response, and helps security engineers deliver verified remediation. Customers use a portal to manage their organization and risk; AEGIS security engineers use a separate operations console to oversee investigations and approve consequential actions.

## Product decisions

| Decision | Baseline |
|---|---|
| Customer market | All industries and organization sizes; policy and compliance profiles are configurable |
| Monitoring | Continuous, 24/7 telemetry processing, detection, alerting and escalation |
| AI authority | Human approval required for consequential response, changes and production remediation |
| Model strategy | Multi-provider, replaceable model adapters; no provider lock-in |
| Product priority | Full platform, delivered in controlled phases |

## Product surfaces

- **Customer portal:** onboarding, organization and asset inventory, integrations, security posture, findings, incidents, reports, remediation approvals and audit history.
- **Security operations console:** tenant-scoped queues, 24/7 alert triage, investigations, assignments, evidence, AI recommendations, approval workflows and customer communications.
- **Platform administration:** tenant lifecycle, plans, integration health, policy templates, access governance, usage and platform audit.
- **AI operations:** orchestrated specialist agents, model routing, evaluation, tool permissions and traceable execution.

## Architecture at a glance

- **Web:** React, TypeScript and Tailwind CSS, deployed on Vercel.
- **API and workers:** Python/FastAPI services and asynchronous workers, deployed on Render.
- **Relational system of record:** Neon Postgres for tenants, identities, assets, findings, incidents, approvals and audit events.
- **AI:** central orchestrator, narrowly scoped agents, provider adapters, evaluation and retrieval services.
- **Telemetry:** streaming/queue-based ingestion and separate scalable event/log storage where volume requires it.
- **Security integrations:** authorized cloud, endpoint, identity, network, source-control and vulnerability-management connectors.

See [Architecture](docs/ARCHITECTURE.md), [Implementation roadmap](docs/ROADMAP.md), and [Security and operations model](docs/SECURITY-MODEL.md).

## Non-negotiable safety principles

1. Tenant isolation is enforced server-side on every data and tool operation.
2. Every customer integration and active security operation requires explicit authorization, scope and revocable credentials.
3. AI may analyze, correlate, recommend and prepare changes; consequential actions require an authorized human approval.
4. Production changes use least privilege, staged rollout where possible, verification, rollback plans and immutable audit evidence.
5. Model providers and security tools sit behind replaceable, permissioned adapters.
6. Secrets never enter source control, prompts, logs or customer-visible reports.
7. Monitoring is continuous; staffing, on-call coverage and response-time commitments are defined by service tier and contract.

## Delivery approach

The complete product is the target, but delivery is incremental: establish secure foundations and the engineer console first, onboard tenants and assets, add continuous telemetry and detection, introduce AI-assisted investigation, then controlled remediation and enterprise-grade operations. See the roadmap for phase exit criteria.

## Repository status

This repository currently contains the product baseline and architecture/roadmap documentation. Application code, deployment configuration, integrations and automated CI are not yet implemented. Documentation describes the intended design, not features already running.
