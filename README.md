# AEGIS

AEGIS is a cybersecurity-focused AI system intended to assist with defensive security operations, investigation, and security analysis.

## Project direction

The implementation is planned in layers so the user interface can be developed first without coupling it to unfinished backend services:

1. **Web UI** — React, TypeScript, and Tailwind CSS.
2. **Python API** — typed service boundaries, authentication, validation, and audit events.
3. **Orchestration** — a central orchestrator that routes requests to narrowly scoped agents.
4. **Model integration** — provider/model adapters behind explicit interfaces.
5. **Memory** — controlled, inspectable storage with retention and access rules.
6. **Security tools** — defensive integrations with permission checks, safe defaults, and traceable tool execution.
7. **Quality and infrastructure** — automated tests, CI, configuration management, observability, and deployment.

This is a roadmap, not a claim that these components already exist.

## Working principles

- Build for authorized, defensive security work.
- Keep model providers and security tools behind replaceable interfaces.
- Require explicit authorization and scope before any active security operation.
- Prefer least privilege, auditable actions, safe defaults, and human approval for consequential actions.
- Never store credentials in source control; use environment-based configuration and managed secrets.
- Keep UI, API, orchestration, agents, memory, and tool adapters independently testable.

## Project workspace

The existing working approach uses Google Drive as the central project workspace and Google Colab for experiments, model evaluation, and training work. This repository is the source of truth for versioned application code and project documentation.

## Repository status

The repository was found empty during the initial implementation audit: no tracked files, commits, branches, pull requests, or project documentation were present. The first repository commit therefore establishes this overview and records the implementation baseline. See [the progress log](docs/PROGRESS.md) for the audit and next task.

## Getting started

The frontend toolchain has not yet been committed. The next implementation task is to establish the React + TypeScript + Tailwind UI foundation, then add a reproducible install/build/test workflow before integrating the Python API.
