# Database layer

The database layer contains SQLAlchemy 2 async models for tenants, memberships and audit records, plus a request-process session-factory lifecycle. PostgreSQL/asyncpg is the intended deployment database; SQLite/aiosqlite is supported only for isolated tests.

Set `AEGIS_DATABASE_URL` in the deployment secret store. Use a PostgreSQL URL in the form `postgresql+asyncpg://...`. Never commit credentials. The setting is represented as a secret and must never be logged.

Tenant selection is a selector, not authority: the API resolves the verified principal's active membership and obtains the tenant UUID and role from the database. Missing, suspended or cross-tenant membership is denied.

Schema migration, PostgreSQL row-level security policies and database role grants are not yet configured. Do not expose tenant-protected production routes until reviewed migrations, RLS policies, database role grants and cross-tenant integration tests are deployed.
