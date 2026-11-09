# Database boundary

This package is reserved for database engine/session lifecycle, migrations, and transaction boundaries. No database driver or connection is configured yet. The future implementation should use managed secrets, TLS, bounded connection pools, migration review, and tenant isolation enforced in the data-access layer. Never accept a tenant identifier from an untrusted request body as the authority for a query.
