# AI service boundary

The AI subsystem is intentionally not connected yet. When implemented, isolate provider adapters, model routing, prompts, agent orchestration, retrieval, evaluation, and safety policy. Treat customer logs, source code, tickets, and tool output as untrusted data. Models are advisory; deterministic policy and authorized human approvals control consequential actions. Prevent cross-tenant context, retrieval, cache, and memory leakage.
