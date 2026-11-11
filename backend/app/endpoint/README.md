# Endpoint agent contract and service (Phase 11)

## Supported capabilities
- Windows, Linux and macOS device descriptors and versioned telemetry envelopes.
- Tenant-admin/security-manager generated enrollment invitations, valid for 5 minutes to 24 hours.
- One-time enrollment redemption; only a SHA-256 token digest is stored.
- Endpoint-generated Ed25519 keypairs; the private key must remain on the endpoint.
- Signed event ingestion, per-device monotonic sequence enforcement, event-ID uniqueness and durable event storage.
- Immediate server-side device revocation and audited invitation/enrollment/revocation lifecycle changes.

## API
- `POST /api/v1/endpoints/invitations` — authenticated tenant manager; returns the raw invitation token once.
- `POST /api/v1/endpoints/enroll` — redeems a token and binds an Ed25519 public key to its tenant.
- `POST /api/v1/endpoints/events` — verifies the event signature against the active registered key, then atomically enforces sequence and persists the event.
- `POST /api/v1/endpoints/{device_id}/revoke` — authenticated tenant manager; revokes only a device belonging to the selected tenant.

The event signature is Ed25519 over the deterministic canonical JSON bytes of the complete `EndpointTelemetryEnvelope`. The signature is sent separately as `signature_b64`. The device ID in the signed envelope is checked against the registered key; tenant identity is always resolved from the database record, never from the client payload.

## Security boundaries
- Device private keys are generated and retained by the endpoint; AEGIS stores only the public key and its SHA-256 fingerprint.
- Enrollment invitations are high-entropy, single-use and short-lived. Raw tokens are never persisted or logged.
- Tenant administration uses verified identity plus persisted membership; caller-supplied tenant IDs are not accepted.
- Event signature verification occurs before the atomic database write. The database re-checks active device status while locking the device row, so a concurrent revocation prevents ingestion.
- Replayed or out-of-order sequence numbers and duplicate event IDs are rejected.
- Database tables are not directly granted to runtime roles; lifecycle operations use narrowly scoped SECURITY DEFINER functions owned by the migration role.
- Deployments must enforce HTTPS and apply gateway-level rate limiting to public enrollment and ingestion routes.

## Current limitations
This increment implements the server-side enrollment and signed telemetry boundary. It does not yet ship native OS collectors, a local agent key store, key rotation, fleet UI, or automated detection rules. OS collectors must use native platform APIs, least privilege, explicit customer configuration and signed updates. No remote shell or arbitrary command execution is part of this agent contract.
