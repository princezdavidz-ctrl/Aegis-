# Tenant profile

Customer tenant profiles are exposed through authenticated, tenant-scoped APIs.

- `GET /api/v1/tenants/profile`: active members can read the profile for the tenant selected by `X-AEGIS-Tenant`.
- `PATCH /api/v1/tenants/profile`: only an active `tenant_admin` can update the profile.

Fields:
- Industry and organization size.
- Region preference.
- Data-retention preference (30–3650 days).
- Policy profile (`baseline`, `strict`, `regulated`).

Reads use the runtime database connection with transaction-local subject/tenant RLS context. Updates use a SECURITY DEFINER function owned by `aegis_migrator`; it rechecks the tenant-admin membership, updates only the server-resolved tenant, and appends an immutable audit event in the same transaction. The API's provisioner role receives EXECUTE only, not direct tenant UPDATE privileges.

**Important:** region is descriptive preference only; it does not yet select a data plane or guarantee data residency. Retention days are stored as a customer preference; automated retention/deletion enforcement is a separate implementation task. Profile fields are metadata, not compliance certification.
