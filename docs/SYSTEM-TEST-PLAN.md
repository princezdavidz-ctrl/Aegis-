# AEGIS System Test and Production Certification Plan

**Status:** Phase 21 — planned/in progress. This document defines the release evidence required; it is not a claim that full system certification has passed.

## 1. Validation levels

| Level | Purpose | Evidence |
|---|---|---|
| Unit | Validate deterministic functions and business rules | Test reports and coverage |
| Component | Validate API, UI, agents and individual engines | Component CI jobs |
| Integration | Validate service, database, identity and connector boundaries | Contract and PostgreSQL integration reports |
| End-to-end | Validate complete user and security workflows | Staging run IDs, trace IDs and signed test evidence |
| Operational | Validate deployment, monitoring, recovery and rollback | Deployment and recovery records |
| Security certification | Validate threat controls and authorization boundaries | SAST/DAST/dependency/secrets reports and reviewed findings |

A green pull-request pipeline is necessary but is not, by itself, full system certification.

## 2. Existing automated CI coverage

The repository currently has automated workflows for:
- Python API tests and module compilation.
- PostgreSQL migrations, tenant RLS and least-privilege role integration.
- React tests, TypeScript typecheck and production build.
- Linux, Windows and macOS endpoint-agent unit tests and compilation.
- Flutter desktop formatting, analysis and widget/unit tests.
- API container build and liveness/readiness smoke tests.
- AWS OIDC Terraform validation.
- Gitleaks, Python/npm dependency audits, CodeQL and NVD catalogue tests.

These checks validate code in CI environments. They do not prove live customer integrations, production AWS deployment, full endpoint installation/upgrade/uninstall, or complete cross-module SOC workflows.

## 3. System test matrix

| ID | Area | Required scenarios | Required evidence |
|---|---|---|---|
| ST-API | API and contracts | Authentication, authorization, schema validation, rate limits, pagination, error handling, readiness/liveness | API test report; contract assertions |
| ST-TENANT | Multi-tenancy | Cross-tenant reads/writes denied; tenant context is server-derived; membership downgrade/revocation takes effect immediately | PostgreSQL RLS integration report |
| ST-DB | Database lifecycle | Upgrade from supported baseline, fresh install, downgrade where supported, backup/restore, concurrent writes, migration-head check | Migration logs; restore verification |
| ST-WEB | Web portal | Sign-in, session expiry, role-based navigation, asset/endpoint workflows, accessibility, browser error handling | Browser E2E report and accessibility findings |
| ST-DESKTOP | Desktop | Startup, authentication, navigation, API disconnect/reconnect, packaging and OS-specific install/remove | Per-OS desktop test evidence |
| ST-ENDPOINT | Endpoint agents | Install, enrollment, signed telemetry, heartbeat, replay rejection, revocation, offline recovery, update, rollback, uninstall | Windows/Linux/macOS test matrix |
| ST-WEBHOOK | Notifications | KMS envelope round-trip, secret rotation/revocation, idempotency, lease expiry, retry classification, pinned-IP TLS, redirect rejection, tenant quotas and kill switch | Fake-KMS tests plus isolated staging receiver report |
| ST-SIEM | SIEM | Ingest, normalize, deduplicate, correlate, search, alert, case lifecycle and evidence export | Synthetic event-to-case trace |
| ST-NDR | NDR | Sensor health, flow/DNS ingestion, asset mapping, detection and alert evidence | Synthetic traffic replay report |
| ST-VM | Vulnerability management | Asset discovery, CVE enrichment, severity prioritization, remediation status and rescan | Scan fixture and remediation trace |
| ST-PENTEST | Authorized testing | Explicit authorization, allowlist/denylist, engagement window, rate limits, safe checks, stop control, evidence and report | Scope-enforcement negative tests and approved lab run |
| ST-AI | AI SOC | Evidence-grounded summaries, retrieval provenance, prompt injection, hallucination checks, tool allowlists, permission denials and human approval | Evaluation report and tool audit trail |
| ST-CLOUD | Cloud security | Read-only IAM/config assessment, least-privilege connector, credential failure and tenant boundary | Isolated AWS test account report |
| ST-IR | Incident response | Dry run, approval, containment, post-action verification, timeout and rollback | Simulated incident playbook trace |
| ST-COMP | Compliance | Control mapping, evidence provenance, owner, timestamps, exceptions and export integrity | Sample audit package |
| ST-OPS | Operations | Load, stress, soak, queue outage, database outage, worker restart, backup restore, deployment rollback and alerting | Load report, recovery objectives and deployment record |

## 4. Mandatory security-negative tests

Every applicable workflow must prove that:
- An unauthenticated or insufficiently privileged actor is denied.
- A tenant cannot access another tenant's data by changing IDs, headers, query parameters or object references.
- Revoked users, devices, tokens and integrations cannot continue operating.
- Replayed, stale, malformed, oversized or tampered requests fail closed.
- Webhook DNS answers containing any non-global address are rejected; connections use a pinned address and hostname-verified TLS.
- Redirects cannot bypass destination validation.
- AI-originated tool calls cannot exceed the caller's permissions or approved tool allowlist.
- Penetration tests cannot run outside explicit engagement scope or time windows.
- Secrets and sensitive payloads do not appear in logs, errors, audit metadata or frontend responses.
- Database and queue failures do not silently acknowledge unprocessed security events.

## 5. Staging execution sequence

1. Provision a dedicated non-production AWS account/environment, isolated PostgreSQL database, test identity provider and synthetic tenant data.
2. Apply migrations from the supported baseline; verify the Alembic graph has one intended head and record the resulting revision.
3. Deploy through GitHub OIDC; verify image digest, TLS, health checks, secrets injection, logging and alarms.
4. Run API, portal and desktop smoke tests using test-only identities.
5. Enroll one supported test endpoint per operating system; validate heartbeat, telemetry, revocation and recovery.
6. Run synthetic event workflows through ingestion, normalization, detection, alert, case and evidence export.
7. Run webhook delivery against a controlled receiver with private-address, redirect, timeout, retry and replay negative tests.
8. Run AI prompt-injection and tool-permission tests using synthetic evidence only.
9. Run load/soak tests, interrupt dependencies, and verify queue recovery, backup restore and rollback.
10. Archive reports, commit SHA, image digest, migration revision, environment identifier and test timestamps.

No production credentials, customer data or unapproved external targets may be used in staging.

## 6. Release gates

A release candidate is not certified until all gates are met:

- All required CI workflows pass on the exact release commit.
- No unresolved Critical or High security findings; accepted exceptions require a named owner, rationale, compensating controls and expiry.
- Tenant isolation, authentication, authorization, revocation and audit tests pass.
- Windows, Linux and macOS endpoint validation is complete for the supported OS versions.
- All in-scope end-to-end workflows pass in staging.
- Backup restore and deployment rollback are demonstrated and meet documented recovery objectives.
- Monitoring, alert routing, operational ownership and incident runbooks are verified.
- Security, performance, accessibility and dependency reports are reviewed and archived.
- Product owner and security owner explicitly approve release evidence.

## 7. Current gaps to close

- Build a repeatable staging environment and automated browser/API E2E suite.
- Add real endpoint installation, upgrade, rollback and uninstall validation on supported OS versions.
- Complete the webhook KMS integration with destination CRUD, rotation, audit and a pinned-IP/TLS delivery worker before enabling notifications.
- Implement and integrate SIEM, NDR, authorized penetration testing, cloud security and incident-response workflows; test only implemented capabilities.
- Add AI tool-permission and prompt-injection regression suites against the live orchestration boundary.
- Add load/soak, queue/database failure injection, backup restore and deployment rollback automation.
- Define supported OS/browser versions, SLOs, RTO/RPO and named release approvers.

## 8. Evidence record template

For each execution, record: test ID, environment, commit SHA, container/image digest, migration revision, test data fixture version, start/end timestamps, result, failed assertions, linked logs/artifacts, defect IDs, owner and retest result. Redact credentials, personal data and customer-sensitive payloads before archiving.
