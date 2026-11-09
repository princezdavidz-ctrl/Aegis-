# AEGIS backend structure

The backend is a modular FastAPI service boundary. This document describes package ownership and intended growth; directories marked as planned are not claims of working integrations or production features.

```text
backend/
├── app/
│   ├── main.py                 # FastAPI application factory / ASGI entry
│   ├── config.py               # validated non-secret settings
│   ├── health.py               # liveness and readiness endpoints
│   ├── api/                    # HTTP transport and route composition
│   │   ├── router.py
│   │   └── v1/
│   ├── security/               # identity, auth verifier, authorization, audit contracts
│   ├── domain/                 # framework-independent domain rules
│   ├── services/               # application use cases
│   ├── repositories/           # tenant-scoped persistence interfaces/adapters
│   ├── db/                     # database lifecycle, sessions, migrations (planned)
│   ├── workers/                # asynchronous jobs and scheduled tasks (planned)
│   ├── integrations/           # authorized security/cloud/SaaS adapters (planned)
│   ├── ai/                     # model gateway, agents, retrieval and evaluations (planned)
│   └── observability/          # privacy-safe logs, metrics and tracing (planned)
├── tests/                      # unit, integration, security and contract tests
├── migrations/                 # reviewed database schema migrations (planned)
├── scripts/                    # local development and maintenance helpers
├── requirements.txt            # pinned runtime dependencies
└── requirements-dev.txt        # pinned development/test dependencies
```

## Runtime boundaries

- **API process:** validates requests, authenticates via a configured trusted adapter, applies exact-scope authorization, and delegates to services.
- **Worker process:** consumes bounded jobs using service identities and the same tenant and authorization policies; it is not an implicit privilege escalation path.
- **Persistence:** PostgreSQL/Neon is the planned transactional system of record. High-volume telemetry and artifacts should use purpose-built event/object storage rather than unbounded relational writes.
- **AI:** provider-independent gateway and narrowly scoped agents. Customer data is tenant-bound and is not used for shared model training without explicit contractual permission and privacy review.
- **Integrations:** read-only by default. Active operations require explicit customer authorization, scoped short-lived credentials, approval, audit, verification, and rollback.

## Tenant isolation requirements

Resolve tenant membership from verified identity and server-side membership records. Never trust a client-provided tenant ID as authorization. Enforce tenant scope in repositories, jobs, caches, object storage, retrieval, model context, and reports. Add negative tests proving that one tenant cannot read or mutate another tenant's resources.

## Delivery sequence

1. Preserve and test the existing configuration, health, identity, authorization, and authentication contracts.
2. Select a concrete identity provider and implement a verified adapter; add durable append-only audit persistence before protected operations.
3. Add database lifecycle, reviewed migrations, tenant membership, and repository isolation tests.
4. Add API contracts and services for onboarding, asset inventory, monitoring configuration, alerts, investigations, and reporting.
5. Add queue workers and read-only integration adapters with explicit customer authorization.
6. Add the model gateway, agent orchestration, retrieval, evaluation, and privacy-safe observability.
7. Add patch proposal workflows and approval gates. Production changes remain disabled until authorization, audit, verification, and rollback are proven.

## Current implementation status

The current application still exposes only liveness and readiness routes. Authentication is a provider-independent interface with no concrete provider configured; authorization and audit are contracts, not a complete protected-operation system. Database, queue, model, worker, and security-tool integrations are not connected. See [backend README](README.md) and the repository progress log for verified status.
