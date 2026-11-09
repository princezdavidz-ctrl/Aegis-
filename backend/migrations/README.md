# Database migrations

Migrations are applied using the separate database migration credential:

```bash
AEGIS_DATABASE_URL='postgresql+asyncpg://...' alembic -c backend/alembic.ini upgrade head
```

The first revision creates tenant, membership and audit tables, forces row-level security, restricts membership reads to the verified subject, scopes audit records to the transaction-local tenant ID, and installs a trigger preventing audit update/delete.

Use a migration-owner role for schema changes and a separate restricted runtime role for the API. Do not grant the runtime role table ownership or bypass-RLS privileges. Test RLS and role grants against Neon/PostgreSQL before enabling tenant-protected API routes.
