# Database layer

The database layer contains SQLAlchemy 2 async models for tenants, memberships and audit records, plus a request-process session-factory lifecycle. PostgreSQL/asyncpg is the intended deployment database; SQLite/aiosqlite is supported only for isolated tests.

Set `AEGIS_DATABASE_URL` in the deployment secret store. Use a PostgreSQL URL in the form `postgresql+asyncpg://...`. Never commit credentials. The setting is represented as a secret and must never be logged.

Run migrations using `alembic -c backend/alembic.ini upgrade head`. The initial migration enables and forces RLS, limits membership reads to the verified subject, limits tenant/audit reads and writes to the transaction-local tenant context, and rejects audit update/delete. The runtime database role must be distinct from the migration owner and granted only necessary privileges.

Tenant selection is a selector, not authority: the API resolves the verified principal's active membership and obtains the tenant UUID and role from the database. Missing, suspended or cross-tenant membership is denied.

The migration still needs to be applied and verified against a dedicated Neon/PostgreSQL test database before production routes are enabled.
