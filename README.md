# AEGIS

AEGIS is a cybersecurity-focused AI system intended to assist with **authorized, defensive security operations**, investigation, and security analysis.

## Project direction

The implementation is layered so each boundary can be developed and tested independently:

1. **Web UI** — React, TypeScript, and Tailwind CSS.
2. **Python API** — typed service boundaries, authentication, validation, and audit events.
3. **Orchestration** — a central orchestrator that routes requests to narrowly scoped agents.
4. **Model integration** — provider/model adapters behind explicit interfaces.
5. **Memory** — controlled, inspectable storage with retention and access rules.
6. **Security tools** — defensive integrations with permission checks, safe defaults, and traceable execution.
7. **Quality and infrastructure** — automated tests, CI, configuration management, observability, and deployment.

This is a roadmap, not a claim that the later components already exist.

## Working principles

- Build for authorized, defensive security work.
- Keep model providers and security tools behind replaceable interfaces.
- Require explicit authorization and scope before active security operations.
- Prefer least privilege, auditable actions, safe defaults, and human approval for consequential actions.
- Never store credentials in source control; use environment-based configuration and managed secrets.
- Keep UI, API, orchestration, agents, memory, and tool adapters independently testable.

## Repository status

The repository contains the first React UI foundation and a local FastAPI service foundation. The UI remains a **local preview** and is not connected to telemetry, models, agents, memory, or security tools. The API currently exposes only liveness and readiness endpoints; it is not deployed and has no authentication, user-data, model, memory, or security-tool routes. See [the progress log](docs/PROGRESS.md) for completed work, validation, limitations, and the next task.

## Web UI development

Requirements: Node.js 20.19+ or 22.12+ and npm.

```bash
npm ci
npm run dev
```

Use `npm ci` for a clean, lockfile-pinned install. After changing dependencies, update `package-lock.json` with `npm install` and commit both dependency files.

Available checks:

```bash
npm test
npm run typecheck
npm run build
```

The dashboard labels all unavailable services as pending and does not fabricate security events or operational metrics. The UI test suite renders the React dashboard and sidebar through Vite SSR to check navigation landmarks, selected-page semantics, native button controls, and visible keyboard focus styling. Browser-driven key-event and viewport testing remains a follow-on quality task.

## Python API development

Requirements: Python 3.11+ and pip.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
uvicorn app.main:app --app-dir backend --reload
```

The API listens on `http://127.0.0.1:8000`. Development documentation is available at `/docs`; it is disabled in the `production` environment. Only `/health/live` and `/health/ready` exist at this stage. Readiness explicitly reports external dependencies as `not_configured` rather than implying that models, databases, or security tools are connected.

The API also contains pure security contracts under `backend/app/security/`: immutable principal and permission models, exact-scope deny-by-default authorization, immutable audit events, and an append-only `AuditEventSink` protocol. These contracts are **not authentication or active enforcement**: no credential verifier, request middleware, protected route, or durable audit store is connected. Only a future trusted authentication adapter may create a `Principal`; caller-supplied identity data must never be trusted. The `tool:execute` permission is a contract only and does not enable tool execution.

Run API tests from the repository root:

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```

The pinned runtime and development dependencies are listed in `backend/requirements.txt` and `backend/requirements-dev.txt`. Current non-secret configuration variables are documented in [the backend README](backend/README.md).

## Project workspace

Google Drive is the central project workspace, and Google Colab is intended for experimentation, model evaluation, and training work. This repository remains the source of truth for versioned application code and project documentation.
