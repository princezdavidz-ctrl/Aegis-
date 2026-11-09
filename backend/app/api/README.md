# API boundary

`api/router.py` is the composition point for versioned HTTP routes. Keep transport schemas separate from domain models. Protected routes must depend on the trusted credential verifier, derive tenant membership from authenticated server-side context, enforce exact permissions, and write a durable audit event before consequential work. The current application intentionally registers only health endpoints.
