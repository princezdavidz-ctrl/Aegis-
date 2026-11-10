# Endpoint agent contract (Phase 11A)

This package defines the initial versioned contract shared by future Windows, Linux and macOS collectors.

## Current scope
- OS descriptor validation for Windows, Linux and macOS.
- Explicit collection profile: minimal, standard or extended.
- Strict event-type allowlist and schema version.
- UUID device/event identifiers and monotonic sequence field.
- Timezone-aware timestamps normalized to UTC.
- JSON-only telemetry payloads bounded to 32 KiB.
- Unknown fields rejected, including client-supplied tenant identifiers.

## Security boundary

These schemas do not authenticate an endpoint, prove device ownership, verify a signature, enroll a device, or persist telemetry. The future ingestion API must authenticate a per-device credential, resolve tenant and asset association server-side, enforce replay/idempotency and revocation, and append an audit record before accepting data. A device ID in a payload is an identifier, not proof of identity.

Collection must be transparent, customer-configured and least-privilege. This contract does not define remote shell, command execution, credential collection, or endpoint response actions.

## Next increment

Implement enrollment challenges, per-device key binding, credential rotation and revocation in the backend before exposing an ingestion route. Then add OS-specific collectors and CI tests on native runners.