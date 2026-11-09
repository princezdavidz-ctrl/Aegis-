# Repository layer

Define narrow persistence interfaces and their implementations here. All reads and writes must be tenant-scoped, parameterized, and covered by cross-tenant isolation tests. Avoid returning secrets or raw telemetry payloads to logs. Durable audit records require append-only semantics and integrity controls.
