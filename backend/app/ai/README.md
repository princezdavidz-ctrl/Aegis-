# AEGIS AI engine

The AI subsystem now contains an initial provider-independent model gateway and an evidence-grounded security-analysis service. It is deliberately not registered as an unauthenticated HTTP endpoint.

## Implemented in this milestone

- Strict Pydantic contracts for bounded security tasks, evidence fragments, findings, severity, confidence, and recommendations.
- OpenAI-compatible chat-completions adapter configured only through server environment variables.
- HTTPS-only provider base URL validation, bounded timeout/output, generic provider errors, and no logging of prompts, responses, or credentials.
- Analysis prompt treats task/evidence as untrusted data, rejects instruction-following from evidence, requires citations to supplied evidence IDs, and makes the model advisory.
- Output is parsed and validated; unsupported evidence references are rejected.
- Human review is always required. No tools, shell, integrations, patching, or response actions are exposed to the model.

## Configuration

Set these server-side environment variables in the deployment secret manager:

| Variable | Required | Purpose |
| --- | --- | --- |
| `AEGIS_AI_API_KEY` | Yes | Provider credential; never commit or expose it to clients |
| `AEGIS_AI_MODEL` | Yes | Exact model identifier supported by the provider |
| `AEGIS_AI_BASE_URL` | No | HTTPS OpenAI-compatible API root; defaults to `https://api.openai.com/v1` |

Never put API keys in source control, desktop compile-time defines, prompts, telemetry, or logs.

## Use in trusted application code

Construct `ModelSettings.from_environment()`, `OpenAICompatibleProvider(settings)`, and `SecurityAnalysisService(provider)` inside a server-side composition boundary. The caller must establish verified identity, tenant membership, authorization, and tenant-scoped evidence retrieval before invoking the service. Do not expose a route until durable fail-closed audit persistence and tenant isolation are implemented.

## Not yet production complete

This milestone is an initial analysis capability, not a complete autonomous SOC. Missing work includes provider-specific integration tests against a controlled staging account, tenant-aware retrieval and memory, prompt-injection and adversarial evaluation suites, telemetry ingestion, agent/tool permission boundaries, durable audit integration, rate/cost controls, model fallback, observability, and human-approved response workflows. Model output is not a source of truth and must never directly execute consequential actions.
