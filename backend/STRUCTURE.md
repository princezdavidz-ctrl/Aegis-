# AEGIS backend structure

The backend is a modular FastAPI service boundary. This document describes package ownership and intended growth; planned components are not claims of working integrations or production features.

```text
backend/
├── app/
│   ├── main.py                 # FastAPI application factory / ASGI entry
│   ├── config.py               # validated non-secret settings + secret DB URL
│   ├── health.py               # liveness and readiness endpoints
│   ├── api/                    # HTTP transport and route composition
│   ├── security/               # identity, auth, authorization, tenant and audit
│   ├── domain/                 # framework-independent domain rules
│   ├── services/               # application use cases
│   ├── repositories/           # tenant membership and audit persistence
│   ├── db/                     # SQLAlchemy models and async session lifecycle
│   ├── workers/                # asynchronous jobs and scheduled tasks (planned)
│   ├── integrations/           # authorized security/cloud/SaaS adapters (planned)
│   ├── ai/                     # model gateway, agents, retrieval and evaluations
│   └── observability/          # privacy-safe logs, metrics and tracing (planned)
├── tests/                      # unit, integration, security and contract tests
└── requirements*.txt           # pinned runtime and development dependencies
```

## Security boundaries

- Tenant identity is derived from verified principal + active persisted membership. A tenant slug from a request is only a selector; tenant UUID and role come from the database.
- Audit records are payload-free and tenant-bound. The SQL sink exposes append only and propagates persistence failures. Production database grants/triggers must also prohibit update/delete.
- The database URL is a secret setting and must come from a secret manager/environment, never source control.
- The API still has no concrete OIDC provider, no protected business routes, no migrations/RLS deployment, and no production customer integrations.

## Delivery sequence

1. Implement trusted OIDC verification and tenant membership management.
2. Add reviewed migrations, PostgreSQL row-level security and database grants.
3. Add protected onboarding, assets, monitoring, alerts and investigation routes with audit-before-action.
4. Add authorized read-only integrations and bounded workers.
5. Add model gateway, agent orchestration, retrieval and evaluations.
6. Add approval-gated patch proposals; production changes remain disabled until verification and rollback are proven.
