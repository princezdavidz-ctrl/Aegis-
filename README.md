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

The repository currently contains the project overview and the first React UI foundation. The UI is intentionally a **local preview**: it does not connect to telemetry, models, agents, memory, or security tools, and it cannot perform security actions. See [the progress log](docs/PROGRESS.md) for the audit, completed work, limitations, and next task.

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

## Project workspace

Google Drive is the central project workspace, and Google Colab is intended for experimentation, model evaluation, and training work. This repository remains the source of truth for versioned application code and project documentation.
