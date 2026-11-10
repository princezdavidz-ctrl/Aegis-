# Tenant membership lifecycle

- `GET /api/v1/tenants/members`: list members for the tenant selected by `X-AEGIS-Tenant`.
- `POST /api/v1/tenants/members/invitations`: create a pending membership for a known OIDC subject, assigning `security_manager`, `analyst` or `viewer`. Invitations expire after seven days.
- `POST /api/v1/tenants/invitations/accept`: the authenticated subject accepts its pending invitation by supplying the tenant slug.
- `PATCH /api/v1/tenants/members/{subject}`: change role, suspend or revoke a member.

All management operations require an active `tenant_admin` membership. Tenant UUIDs are resolved from persisted membership; callers cannot supply them. Database SECURITY DEFINER functions recheck tenant-admin authority and perform each write and audit event atomically. The provisioner role has EXECUTE on these functions only and no direct table privileges.

The database prevents removal or demotion of the last active tenant administrator. Membership mutations append immutable tenant-scoped audit events.

**Limitation:** invitations are pending grants to known OIDC subjects. This does not send email or create identity-provider accounts. An administrator must obtain the exact subject through a trusted IdP process. The invitee must authenticate as that subject to accept. Email and IdP invitation integration remain a later connector task.

Apply migration `0003_membership_lifecycle` using `aegis_migrator`, then re-run `deploy/postgres/grants.sql` so `aegis_provisioner` receives EXECUTE on the new functions. Do not grant it direct table access.
