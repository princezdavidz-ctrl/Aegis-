# Security boundaries

Current contracts include verified-principal injection, exact-scope authorization, tenant membership resolution, immutable tenant context and a payload-free audit event.

The current application still has no concrete identity provider configured and does not expose protected business routes. Configure a trusted OIDC verifier and production database before using tenant context in production. Do not trust caller-supplied tenant IDs or identity headers.
