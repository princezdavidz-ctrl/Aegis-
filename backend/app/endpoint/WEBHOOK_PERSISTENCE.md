# Webhook persistence foundation

Migration `0013_webhook_delivery_outbox` introduces tenant-scoped persistence
for outbound endpoint notifications.

## Security contract

- A destination stores only `secret_ciphertext`, a KMS key reference, an
  encryption-format version and a monotonically increasing secret version.
  Plaintext signing secrets and raw KMS key material must never be persisted.
- The encryption envelope is intentionally not implemented by this migration.
  Destination creation/rotation must remain unavailable until a configured
  KMS/envelope-encryption provider is available and tested.
- Destination and outbox rows carry tenant IDs. The outbox uses a composite
  foreign key so a delivery cannot reference another tenant's destination.
- A tenant/idempotency-key unique constraint prevents duplicate event enqueue.
- Outbox state, bounded attempts, due-time index and lease fields support a
  future competing-consumer worker without making delivery active today.
- RLS permits manager-role reads only. Application and worker roles receive no
  table privileges in this migration; narrowly scoped database functions and a
  dedicated worker role are required before runtime access.
- The payload is bounded to 1 MiB and must be a JSON object. Error storage is
  limited to a short code; never store response bodies, credentials or headers.

## Delivery remains disabled

This schema does not create an API, KMS integration, queue consumer, HTTP
client, retry scheduler or notification delivery. A future worker must:
resolve DNS immediately before each attempt; reject every non-global address;
connect directly to a pinned address while retaining the original hostname for
TLS SNI and certificate validation; disable redirects; enforce connect/read
timeouts and response-size limits; and use a lease token for compare-and-set
state transitions. Delivery must remain feature-disabled until those controls,
tenant quotas, a kill switch, audit events and integration tests are in place.

## Migration ordering

The revision follows `0012_endpoint_heartbeat_health`, the current endpoint
heartbeat head. It does not assume a cloud KMS is configured.
