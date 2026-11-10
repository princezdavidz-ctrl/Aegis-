# Repositories

Repositories isolate persistence from HTTP handlers and application services.

Implemented in this phase:
- active tenant membership lookup by verified subject and tenant slug;
- append-only API surface for durable audit event insertion.

The tenant UUID and role are loaded from persisted membership; a request-supplied tenant selector never grants access by itself. Database-level row security, migrations, and additional repositories remain pending.
