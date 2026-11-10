# API routers

Versioned feature routers are registered in `app.main` only after authentication,
server-derived tenant membership, exact-scope authorization, bounded input and
durable audit requirements are implemented.

The advisory AI route is mounted at `POST /api/v1/ai/analysis`. It requires
`investigation:create`, a verified identity, an active persisted tenant
membership selected by `X-AEGIS-Tenant`, an injected specialist runtime, and a
durable audit store. The tenant UUID is never accepted from the request body.

The specialist runtime is injected through `app.state.specialist_analysis_service`;
the API intentionally fails closed with 503 until a real provider-backed adapter
is configured. It never executes tools or production changes.
