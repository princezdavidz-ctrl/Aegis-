# Endpoint device identity primitives (Phase 11B foundation)

This module provides cryptographic building blocks for the future device registry.

- Generate high-entropy one-time enrollment tokens and store only SHA-256 digests.
- Compare enrollment tokens in constant time.
- Verify Ed25519 signatures over deterministic canonical telemetry envelopes.
- Reject malformed public keys/signatures and invalid signatures.

## Required server-side lifecycle (not implemented by these primitives)

1. A tenant administrator creates an expiring, single-use enrollment invitation.
2. The database stores only its token digest, tenant, allowed OS/profile, creator, expiry and consumed state.
3. The endpoint generates its Ed25519 private key locally; the private key never leaves the device.
4. The server redeems the invitation transactionally, binds the public key and device identity to the invitation's tenant, and consumes the invitation exactly once.
5. The ingestion service authenticates every event using the registered public key, verifies the signature and enforces a durable per-device sequence/replay constraint.
6. Revocation and credential rotation invalidate the device immediately; all lifecycle changes are durably audited.

Never trust a tenant ID, device ID, public key, or claimed role from an unauthenticated event. Device identity must be resolved from the authenticated registry record. These helpers do not persist enrollment state, enforce expiry, prevent replay, authenticate HTTP requests, or provide a complete endpoint enrollment service.

## Cryptographic format

- Ed25519 raw public key: 32 bytes, standard Base64.
- Signature: 64 bytes, standard Base64.
- Signature input: UTF-8 JSON from the validated schema, sorted keys, compact separators, ASCII escaping, and NaN disabled.
- Enrollment token: 32 random bytes encoded with URL-safe Base64; store SHA-256 hex digest only.
