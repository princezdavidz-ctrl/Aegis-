# Engineer Desktop Architecture

The Flutter client is a presentation and workflow surface. The FastAPI backend is authoritative for identity, tenant membership, permissions, policy, approvals and audit records.

## Feature modules
Each module owns presentation, domain contracts, application state/providers and data adapters as it becomes functional. Shared code belongs in core or shared only when genuinely cross-feature.

## Data handling
- Never trust tenant IDs or role claims supplied by local UI state.
- Bind every request to a server-validated authenticated session.
- Do not persist access tokens in ordinary preferences or logs.
- Use platform secure storage only after the backend authentication contract is selected.
- Redact secrets and sensitive customer data from diagnostics.
- Treat telemetry, source code, tickets and agent outputs as untrusted data.

## Consequential actions
Production response and patch deployment controls remain unavailable until backend authorization, explicit scope, short-lived credentials, human approvals, durable audit, verification and rollback are implemented.

## Realtime
Realtime transport is abstracted behind RealtimeGateway. Reconnect, backpressure, event ordering, tenant filtering and replay cursors must be defined before production use.
