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
