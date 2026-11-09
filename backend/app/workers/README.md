# Background workers

Future workers process queued telemetry, scheduled scans, enrichment, report generation, and integration synchronization. Workers must authenticate as narrowly scoped service principals, enforce tenant isolation per message, be idempotent, bound retries, use dead-letter handling, and emit traceable audit records. Do not start active scans or response actions without a separately approved authorization scope.
