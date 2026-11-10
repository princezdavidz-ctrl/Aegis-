# AEGIS Expansion Threat Model

## Assets to protect
- Customer identity, tenant records, endpoint and cloud inventory.
- Endpoint/network telemetry, source code, vulnerabilities, pentest findings and incident evidence.
- Connector credentials, agent private keys, signing keys and model-provider credentials.
- Engagement authorization, target scope, action approvals and audit history.

## Trust boundaries
1. Customer endpoint agent to ingestion API.
2. Customer connector to AEGIS connector workers.
3. Tenant event pipeline to storage, queues, search and AI retrieval.
4. Pentest scheduler to assessment adapters and target networks.
5. AI orchestrator to typed tools and approval service.
6. Engineer workstation/customer portal to backend APIs.
7. Build pipeline and update-signing infrastructure to installed agents.

## Principal threats and required controls

| Threat | Required control |
|---|---|
| Agent impersonation or stolen device key | Per-device identity, signed challenges, rotation, revocation, replay protection and short-lived tokens |
| Cross-tenant telemetry injection | Derive tenant from authenticated device membership; ignore client tenant IDs; RLS and isolation tests |
| Malicious telemetry or prompt injection | Treat all collected content as untrusted; strict schemas; no instruction following from evidence |
| Agent supply-chain compromise | Reproducible builds, code signing, protected release workflow, staged rollout and rollback |
| Unauthorized pentest target | Written authorization, verified ownership, immutable allowlist, exclusions and scope enforcement in every adapter |
| Pentest causing outage | Safe profiles, rate limits, concurrency caps, test windows, kill switch and no DoS/destructive tests |
| Scanner escape or arbitrary command execution | No arbitrary shell; isolated workers; typed adapter operations; strict egress allowlists |
| Connector credential theft | Secret manager, least privilege, short-lived credentials, redaction, rotation and audit |
| Event replay/flooding | Nonce/sequence, idempotency, quotas, bounded payloads, queue back-pressure and abuse monitoring |
| AI-triggered harmful action | Advisory-only agents; deterministic policy; independent human approval; payload binding and rollback |
| Evidence leakage in reports/search | Tenant-scoped retrieval/export, access checks, audit, retention and redaction |
| Compromised CI/update signing | Protected branches/environments, isolated signing, provenance and release approvals |

## Security invariants
- No tenant ownership is accepted from untrusted client payloads.
- No agent receives a general-purpose shell or unrestricted administrative API.
- No pentest runs without a current, target-specific authorization record.
- No disruptive response action executes without policy approval and a human approval from the required authority.
- No customer evidence is shared with another tenant or used for shared model training by default.
- Every privileged operation is attributable and durably audited.
