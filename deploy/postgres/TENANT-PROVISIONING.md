# Tenant provisioning database boundary

AEGIS tenant creation is a platform-level operation, not an ordinary tenant-scoped API write. It must not be performed using the normal `aegis_runtime` database credential.

## Roles

- `aegis_migrator` owns schema objects and runs reviewed Alembic migrations. It is non-superuser and `NOBYPASSRLS`.
- `aegis_runtime` reads tenant/membership data and appends audit events. It has no tenant or membership INSERT privileges.
- `aegis_provisioner` has no table privileges. It can execute only `public.aegis_provision_tenant(...)`, a fixed SECURITY DEFINER function owned by `aegis_migrator`.

The SECURITY DEFINER function runs with the migration owner's identity, uses a fixed search path, validates every argument, inserts the tenant and initial `tenant_admin` membership, sets transaction-local RLS context, and appends the provisioning audit event in the same transaction. If any insert fails, the transaction rolls back.

The API exposes `POST /api/v1/tenants` only to a verified principal with the exact `tenant:provision` permission. The API uses a separate `AEGIS_PROVISIONER_DATABASE_URL` connection. The request cannot supply the tenant UUID or actor identity; both are server-derived. The initial administrator subject is an explicit request field, validated and stored as a membership.

## Provisioner credential

After applying migration `0002_tenant_provisioning` and running `deploy/postgres/grants.sql`, set a separate password for `aegis_provisioner` using the secret-management process. Configure that connection only as `AEGIS_PROVISIONER_DATABASE_URL` in the API service. Do not reuse the migration-owner or runtime credential.

The provisioner role must remain `NOSUPERUSER NOBYPASSRLS` and must not receive direct table privileges. The database function is the only supported write path for tenant creation. Membership invitations, role changes, suspension and revocation require separate audited APIs and are not included in this first vertical slice.

## Audit and trust boundary

The database function records the verified platform actor subject, actor type, request correlation ID, tenant ID and successful action in `audit_events`. The API authorizes the `tenant:provision` scope before it calls the function. This assumes the API's OIDC verifier and provisioner secret remain trusted; the database function does not independently validate external identity tokens.

A live Neon integration and production OIDC provider must still be configured and verified before enabling this route for real customers.
