# AEGIS API

FastAPI service foundation with health endpoints, provider-independent authentication contracts, an optional OIDC/JWKS verifier, deny-by-default permission checks, tenant membership resolution and durable audit persistence.

## Local development

```bash
python -m venv .venv
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest backend/tests -q
uvicorn app.main:app --app-dir backend --reload
```

## OIDC authentication

Configure all three values together in the deployment environment:
- `AEGIS_OIDC_ISSUER`
- `AEGIS_OIDC_AUDIENCE`
- `AEGIS_OIDC_JWKS_URL`

The verifier accepts RS256 JWTs only, validates signature, issuer, audience, expiry and required claims, and maps only known AEGIS scopes. Unknown scopes do not grant capabilities. JWKS network failures fail closed as authentication unavailable. No provider is selected or configured by default.

## Database and migrations

Set `AEGIS_DATABASE_URL` in the environment or deployment secret store to a PostgreSQL/asyncpg connection URL. Never commit credentials. SQLite/aiosqlite is used only in tests.

Run reviewed schema migrations with:

```bash
AEGIS_DATABASE_URL='postgresql+asyncpg://...' alembic -c backend/alembic.ini upgrade head
```

The migration enables and forces PostgreSQL row-level security for tenant, membership and audit tables. The request tenant context sets transaction-local subject and tenant values used by the policies. The audit table also receives a trigger that rejects update/delete.

Use a restricted application database role that does not own tables and has only required privileges. Keep the migration owner credentials separate from runtime credentials.

## Security status

The current API still exposes health routes only. No protected customer-data route or live customer integration is connected. RLS/migration behavior is covered by PostgreSQL migration design but still requires a live Neon/PostgreSQL integration test before production use. Configure a trusted OIDC provider and Neon connection in deployment secrets; do not commit credentials.
