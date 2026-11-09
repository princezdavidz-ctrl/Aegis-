# AEGIS

**AI-assisted, human-governed cybersecurity operations for organizations of every size and industry.**

AEGIS is a multi-tenant managed security platform for continuous monitoring, threat detection and investigation, and approval-controlled remediation. It has three application surfaces: a customer portal, an engineer SOC desktop, and backend/AI services.

## Repository layout

```text
Aegis-/
├── frontend/                 # React + TypeScript customer/operations web portal
├── backend/                  # FastAPI API and security contracts
├── apps/
│   └── engineer-desktop/      # Flutter engineer SOC workstation
├── services/
│   └── ai/                    # AI service architecture and initial contracts
├── docs/                      # Architecture, roadmap, security and progress
└── .github/workflows/         # Web/API and Flutter CI
```

## Technology

- **Frontend:** React, TypeScript, Vite and Tailwind CSS; deploy the `frontend/` directory as the Vercel project root.
- **Backend:** Python 3.11+, FastAPI; deploy the `backend/` application on Render.
- **Engineer desktop:** Flutter for Windows, Linux and macOS.
- **Database target:** Neon PostgreSQL. No live database connection is configured yet.
- **AI:** provider-independent architecture under `services/ai/`; no live model provider or agent execution is configured yet.

## Local development

Web portal:

```bash
cd frontend
npm ci
npm test
npm run typecheck
npm run build
npm run dev
```

API:

```bash
python -m venv .venv
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest backend/tests -q
uvicorn app.main:app --app-dir backend --reload
```

Flutter desktop:

```bash
cd apps/engineer-desktop
flutter pub get
flutter analyze
flutter test
```

## Security principles

1. Resolve tenant identity and membership on the server; never trust client-supplied tenant IDs.
2. Default integrations to read-only and require explicit customer authorization and scoped credentials.
3. Treat model output as advisory. Consequential actions require deterministic policy checks and human approval.
4. Audit protected operations durably before enabling them; verify outcomes and provide rollback.
5. Keep customer data isolated across storage, retrieval, prompts, queues, caches and reports.
6. Treat logs, source code, tickets and tool output as untrusted content; defend against prompt injection.
7. Never commit secrets or place credentials in prompts or logs.

## Verified implementation status

This repository now contains the web UI foundation, a modular FastAPI foundation, a Flutter desktop scaffold and AI architecture boundaries. These are early foundations, not a production-ready security platform:

- The API currently exposes health endpoints only. It now includes an optional OIDC/JWKS verifier, tenant-membership resolution, SQLAlchemy persistence models, a tenant-bound audit sink, and PostgreSQL RLS migrations; no identity provider or database is configured, migrations have not been applied to Neon, and no protected business routes are exposed.
- The web portal is a frontend foundation; production authentication and backend data workflows are not connected.
- The Flutter workstation is a structural scaffold; live SOC telemetry and operational actions are not connected.
- The AI service is primarily architecture/contracts; no production model provider, agent orchestration or security-tool execution is connected.
- Database, telemetry ingestion, customer integrations and production deployment are not configured.

See [Architecture](docs/ARCHITECTURE.md), [Roadmap](docs/ROADMAP.md), [Security model](docs/SECURITY-MODEL.md), and [Progress](docs/PROGRESS.md).
