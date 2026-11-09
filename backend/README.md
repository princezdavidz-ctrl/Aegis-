# AEGIS API

FastAPI service foundation with health endpoints, provider-independent authentication contracts, deny-by-default permission checks, tenant membership lookup and durable audit persistence boundaries.

## Local development

```bash
python -m venv .venv
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest backend/tests -q
uvicorn app.main:app --app-dir backend --reload
```

## Database

Set `AEGIS_DATABASE_URL` in the environment or deployment secret store to a PostgreSQL/asyncpg connection URL. Never commit credentials. SQLite/aiosqlite is used only in tests.

The tenant selector header is resolved against the verified principal's active membership. The returned tenant UUID and role come from the database. A selector alone does not authorize access.

## Security status

The current API still exposes health routes only. There is no concrete OIDC identity provider configured, no protected customer data route, no reviewed production migration/RLS deployment, and no live customer integration. Audit writes are implemented as an append-only application adapter but must be combined with database grants/triggers and production migrations before use for protected actions.
