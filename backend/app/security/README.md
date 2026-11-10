# Security boundaries

The API provides a provider-independent verifier contract and an optional OIDC RS256/JWKS adapter. It validates issuer, audience, signature, expiry and required claims. Only recognized AEGIS scopes are mapped into permissions.

Tenant authority is resolved from a verified principal's active membership. PostgreSQL RLS uses transaction-local subject and tenant settings. A request-supplied tenant slug is only a selector; tenant UUID and role come from persisted membership.

Audit records are payload-free, tenant-bound and append-only at both the application API and PostgreSQL trigger layer. Runtime database credentials must be restricted and separate from migration-owner credentials.

No protected customer-data routes are exposed yet. Verify migrations and RLS against a real Neon/PostgreSQL test database before production use.
