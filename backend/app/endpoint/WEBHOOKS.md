# Endpoint webhook delivery security contract

The endpoint webhook primitives provide:

- HTTPS-only destination validation and rejection of URL credentials, query
  strings, fragments, non-443 ports, IP-literal hosts and obvious local names.
- HMAC-SHA256 signatures over the exact body and Unix timestamp, versioned as
  `v1=<hex digest>`.
- Constant-time signature comparison and a bounded timestamp tolerance.
- Bounded exponential retry-delay calculation.

## Important delivery requirements

These primitives are not a complete webhook delivery service. Before enabling
network delivery, the worker and persistence layer must implement all of the
following:

1. Resolve destination DNS at delivery time; reject every non-global address,
   including private, loopback, link-local, multicast, reserved and IPv4-mapped
   IPv6 addresses. Pin the selected public address for the connection and
   verify the TLS hostname/certificate against the original DNS name. Re-check
   redirects or disable redirects entirely.
2. Store signing secrets encrypted with a managed key (for example KMS); never
   store plaintext secrets or expose them in API responses/logs. Support
   rotation and revocation.
3. Persist an outbox event before acknowledging the source transaction. Use a
   stable event ID as the idempotency key and retain immutable delivery attempts.
4. Retry transient network errors and 5xx responses with bounded exponential
   backoff; do not retry permanent 4xx responses indefinitely. Enforce per-tenant
   quotas, request timeouts, payload limits and a global kill switch.
5. Record delivery status, response class, attempt count and timestamps without
   recording response bodies, credentials or signing secrets.
6. Sign each attempt with a fresh timestamp. Receivers must reject stale
   timestamps and deduplicate event IDs to prevent replay.

The current change intentionally supplies the cryptographic and URL-validation
building blocks only. It does not claim that webhook destinations are persisted
or that notifications are being delivered.
