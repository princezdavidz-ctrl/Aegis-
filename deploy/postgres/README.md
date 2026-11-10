# PostgreSQL role separation

AEGIS must use distinct database identities for schema migrations and API runtime access. Never run the API as a PostgreSQL superuser, a `BYPASSRLS` role, or a table owner.

## Roles

- `aegis_migrator`: non-superuser migration identity. Owns tables created by Alembic and has schema CREATE permission. Use only for a separately reviewed migration task.
- `aegis_runtime`: non-superuser application identity. Has SELECT on tenant/membership and audit tables, plus INSERT on audit events. It has no UPDATE/DELETE permission on audit events and is not a table owner.
- No production `BYPASSRLS` role is created. Both identities are explicitly set to `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, and `NOBYPASSRLS`.

## Provision roles

Run as a database administrator connected to the dedicated AEGIS database. Supply the database name as a psql variable:

```sh
psql "$AEGIS_ADMIN_DATABASE_URL" -v db_name=aegis -v ON_ERROR_STOP=1 -f deploy/postgres/roles.sql
```

Set independent strong passwords using an approved secret-management process. With interactive psql, use `\\password aegis_migrator` and `\\password aegis_runtime`; store the resulting connection strings in the deployment secret manager, not in Git or application logs.

## Apply migrations

Run the Alembic migration using the `aegis_migrator` connection:

```sh
AEGIS_DATABASE_URL="$AEGIS_MIGRATION_DATABASE_URL" alembic -c backend/alembic.ini upgrade head
```

Then grant the API runtime role its deliberately limited privileges as the migration owner:

```sh
psql "$AEGIS_MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f deploy/postgres/grants.sql
```

Configure the API's `AEGIS_DATABASE_URL` with the `aegis_runtime` connection, never the migration-owner connection.

## Permission boundary

- Runtime may resolve active memberships and read tenant-scoped rows through the existing RLS policies.
- Runtime may append audit events. Database RLS binds writes to the transaction-local tenant context, and the audit trigger rejects UPDATE/DELETE.
- Runtime cannot create tenants or memberships yet. Phase 2 must introduce a controlled, audited provisioning boundary before granting those permissions.
- New tables receive SELECT by default only. Any write grants must be explicit, reviewed, and accompanied by RLS policies and integration tests.

## Verification

The GitHub Actions PostgreSQL integration suite creates a separate CI-only mutation role to prove the audit trigger rejects UPDATE/DELETE even when a role has those table privileges. That role and its test passwords are never used in production.

Use a dedicated Neon development database to verify this role design before staging. The CI test does not prove that any live Neon database has been configured.
