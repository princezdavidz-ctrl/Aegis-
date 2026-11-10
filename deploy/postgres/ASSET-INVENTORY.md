# Tenant asset inventory

- `GET /api/v1/assets`: list assets for the active tenant; supports `include_archived`, `limit` and `offset`.
- `POST /api/v1/assets`: create a manually registered asset.
- `PATCH /api/v1/assets/{asset_id}`: update metadata or archive the asset.

Supported types include cloud accounts, endpoints, servers, domains, repositories, networks, applications, databases, user identities and other assets. Environment and criticality use bounded enumerations.

All reads require an authenticated active tenant membership and use transaction-local tenant RLS context. Only `tenant_admin` and `security_manager` roles can create, update or archive assets. Writes use database SECURITY DEFINER functions that re-check the role, set tenant context, and append immutable audit events atomically. The provisioner database role has EXECUTE only and no direct asset table privileges. Asset RLS additionally checks that the authenticated subject has active membership in the selected tenant.

**Scope limitation:** this is a manual inventory foundation. Cloud/endpoint discovery, connector authorization, continuous synchronization, ownership mapping, evidence provenance and ingestion health are not implemented here. Asset registration does not itself verify that the asset exists or is under customer control; connector-based proof of authorization is a later task.
