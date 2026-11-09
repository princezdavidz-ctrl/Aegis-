# AEGIS AI Service

The AEGIS AI service is the platform's security-intelligence layer. It coordinates specialist agents, model providers, tenant-scoped knowledge retrieval, approved security tools, evaluation and auditable workflows.

## Design principles
- Tenant context is established by trusted server-side identity, never by an untrusted request field.
- Agents are advisory by default and use permissioned tools.
- Read-only operations are the default. Consequential writes pass policy and human-approval gates.
- Every finding and action is evidence-linked, traceable and attributable to an agent/model version.
- Customer data is isolated across retrieval, prompts, storage, evaluation and observability.
- Model providers are interchangeable behind a stable gateway.

## Initial implementation order
1. Core contracts, configuration and health.
2. Model gateway and provider adapters.
3. Tenant-scoped knowledge and retrieval.
4. Orchestrator, registry and specialist agent contracts.
5. Detection and investigation workflows.
6. Approval-gated tools and patch sandbox.
7. Evaluation, feedback and production observability.

This directory initially defines the architecture boundary. Functional agents and integrations will be implemented and tested incrementally.
