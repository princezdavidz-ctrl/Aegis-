# AEGIS Python API

This directory contains the first, intentionally small FastAPI service boundary. It currently exposes only non-sensitive process health endpoints; it does not authenticate users, access telemetry, call models, retain memory, or execute security tools.

## Requirements

- Python 3.11 or newer
- pip

## Local development

From the repository root:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
uvicorn app.main:app --app-dir backend --reload
```

The API listens on `http://127.0.0.1:8000` by default. In development, interactive API documentation is available at `/docs`.

## Health contracts

- `GET /health/live` confirms that the ASGI process can answer requests.
- `GET /health/ready` reports application readiness and explicitly marks external dependencies as `not_configured` until real dependency checks exist.

These endpoints are deliberately unauthenticated and return no user or infrastructure secrets. They are not proof that model, database, memory, or security-tool services are operational.

## Configuration

All current settings are optional and non-secret:

| Variable | Allowed values / default | Purpose |
| --- | --- | --- |
| `AEGIS_APP_NAME` | `AEGIS API` | Service title (1–80 non-whitespace characters) |
| `AEGIS_ENVIRONMENT` | `development`, `test`, `staging`, `production` | Runtime environment |
| `AEGIS_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Process log threshold |

Invalid values fail configuration validation during application construction. In `production`, interactive docs and the OpenAPI document are disabled. Do not put credentials or private data in these settings.

## Tests

From the repository root:

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```

Authentication, scoped authorization, audit events, persistent storage, orchestrator routes, model adapters, and security-tool integrations remain future work. Protected endpoints must not be added until those controls and their tests are in place.


## Security contracts (not active authentication)

The `app.security` package currently provides small, framework-independent contracts:

- `Principal` is an immutable identity assertion intended to be constructed only by a future trusted authentication adapter. Constructing one does not authenticate a request.
- Principals have an empty permission set by default. Authorization grants only an exact declared permission; missing identity, missing scope, wildcard scopes, and unknown scopes are denied or rejected.
- `AuditEvent` is immutable, requires timezone-aware timestamps, and contains only bounded opaque identifiers and action/resource labels. Extra fields such as request bodies are rejected.
- `AuditEventSink` exposes only an asynchronous append operation. It is a protocol, not a storage implementation; no events are currently persisted.

No authentication verifier, request middleware, protected API route, or durable audit store is wired. Do not accept a principal from a request body or unverified header. Before any protected operation is introduced, add a trusted verifier and request identity boundary, then a durable append-only audit adapter that fails closed when persistence is unavailable. The `tool:execute` permission does not authorize or execute any tool by itself.
