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
│   └── ai/                    # Provider-neutral AI gateway and specialist workflows
├── deploy/aws/                # AWS OIDC deployment foundation
├── docs/                      # Architecture, roadmap, security, progress and backlog
└── .github/workflows/         # Web, API, AI, Flutter and manual AWS deployment CI
```

## Technology

- **Frontend:** React, TypeScript, Vite and Tailwind CSS; deploy the `frontend/` directory as the Vercel project root.
- **Backend:** Python 3.11+, FastAPI; deploy the `backend/` application.
- **Engineer desktop:** Flutter for Windows, Linux and macOS.
- **Database target:** Neon PostgreSQL; migrations and RLS are in source but no live database is configured or verified.
- **AI:** provider-independent gateway and advisory specialist workflows under `services/ai/`; live provider configuration is not confirmed.
- **AWS:** manual GitHub Actions deployment foundation using short-lived GitHub OIDC credentials; infrastructure provisioning and a successful live deployment are not confirmed.

OIDC configuration uses `AEGIS_OIDC_ISSUER`, `AEGIS_OIDC_AUDIENCE` and `AEGIS_OIDC_JWKS_URL` together. Optional `AEGIS_OIDC_CLOCK_SKEW_SECONDS` defaults to 30 seconds. Optional `AEGIS_OIDC_JWKS_CACHE_SECONDS` defaults to 300 seconds and is bounded from 30 to 600 seconds. Production OIDC endpoints must use HTTPS; loopback HTTP is allowed only in development/test environments.

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

AI service:

```bash
python -m pip install -e services/ai
python -m pytest services/ai/tests -q
```

## Verified implementation status

The repository contains meaningful foundations, but it is not yet a production-ready security platform:

- **API:** FastAPI app factory, health routes, optional OIDC/JWKS verification, server-side membership resolution, tenant-aware SQLAlchemy sessions, PostgreSQL RLS migrations, durable audit adapter boundaries, and authenticated advisory AI analysis endpoint are present. A live IdP/database is not configured; PostgreSQL migrations/RLS are not yet verified against a live database.
- **Web portal:** React/TypeScript/Tailwind portal includes overview, Organization profile, tenant-scoped Asset Inventory and tenant Member Management screens. A React OIDC session provider now wires the provider-neutral Authorization Code + PKCE adapter into the shell, handles the callback, and exposes sign-in/local sign-out state. Sign-in stays disabled until a complete public IdP configuration is supplied. A verified identity alone does not establish tenant membership; customer data pages remain locked until the API resolves membership server-side.
- **Flutter desktop:** engineer SOC shell and module navigation are present. Live SOC telemetry and operational workflows are not connected.
- **AI:** provider-neutral model gateway, OpenAI-compatible adapter, specialist analysis workflows and backend runtime wiring are present. No live model provider or customer evidence retrieval is confirmed.
- **Telemetry/detection:** real customer connectors, event ingestion, detection and correlation are not yet operational.
- **AWS:** OIDC deployment workflow and role Terraform foundation are present. AWS resources have not been provisioned and a successful deployment has not been confirmed.

## Security principles

1. Resolve tenant identity and membership on the server; never trust client-supplied tenant IDs.
2. Default integrations to read-only and require explicit customer authorization and scoped credentials.
3. Treat model output as advisory. Consequential actions require deterministic policy checks and human approval.
4. Audit protected operations durably before enabling them; verify outcomes and provide rollback.
5. Keep customer data isolated across storage, retrieval, prompts, queues, caches and reports.
6. Treat logs, source code, tickets and tool output as untrusted content; defend against prompt injection.
7. Never commit secrets or place credentials in prompts or logs.
8. Use GitHub OIDC for AWS deployment; do not use long-lived AWS access keys.

## Project planning

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Implementation backlog and GitHub phase issues](docs/IMPLEMENTATION-BACKLOG.md)
- [Security model](docs/SECURITY-MODEL.md)
- [Progress log](docs/PROGRESS.md)
- [AWS deployment prerequisites](deploy/aws/README.md)


## Continuous integration and security checks

Pull requests are validated with frontend tests/typechecking/build, Python API tests, PostgreSQL migration and row-level security integration tests, API container smoke tests, Flutter format/analyze/widget tests, and AWS Terraform formatting/validation.

The security workflow adds:
- Gitleaks secret scanning across repository history.
- Python dependency vulnerability audits for backend and AI runtime requirements.
- npm dependency audit for the locked frontend dependency tree.
- CodeQL static analysis for Python and JavaScript/TypeScript.
- Weekly scheduled security scans.

A passing scan is evidence only for the scanned commit and dependency advisory database at scan time; it does not replace penetration testing or runtime monitoring.


## Tenant onboarding boundary

The first platform-level onboarding operation is POST /api/v1/tenants. It requires a verified tenant:provision scope and a separate AEGIS_PROVISIONER_DATABASE_URL connection. Tenant creation, initial tenant_admin membership and the provisioning audit event are committed atomically by a restricted PostgreSQL function. A live identity provider and Neon database are still required before production use.
