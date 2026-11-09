# AEGIS AI runtime

The AI runtime provides a provider-neutral model gateway and four fixed-purpose
specialist analysis agents. It is advisory-only: there is no model tool-calling
surface, shell access, security-tool execution, patch deployment, or autonomous
remediation.

## Specialist agents

- **Alert triage** — severity/confidence assessment, benign explanations,
  missing telemetry and validation recommendations.
- **Threat intelligence** — indicator context, confidence/freshness limitations,
  false-positive considerations and defensive validation.
- **Vulnerability analysis** — environment-specific exploitability, exposure,
  compensating controls and risk-ranked remediation proposals.
- **Incident investigation** — evidence-based timelines, facts vs. hypotheses,
  scope uncertainty and evidence-preserving next steps.

All specialists use the shared `ModelGateway`. The orchestrator dispatches to
one allow-listed specialist per request; agents do not call one another and
cannot invoke tools or perform actions. Outputs carry evidence IDs and are
marked advisory-only and requiring human review.

## Install and test
```bash
cd services/ai
python -m pip install -e '.[dev]'
python -m pytest
```

## Configure a provider

Set these values in the deployment secret manager (never commit them):
- `AEGIS_AI_PROVIDER`: provider label, default `openai-compatible`
- `AEGIS_AI_BASE_URL`: HTTPS API base URL, default OpenAI API base
- `AEGIS_AI_MODEL`: model identifier supplied by the chosen provider
- `AEGIS_AI_API_KEY`: provider credential
- `AEGIS_AI_TIMEOUT_SECONDS`: request timeout, 1–120 seconds
- `AEGIS_AI_MAX_OUTPUT_TOKENS`: output cap, 1–8192

The adapter uses the OpenAI-compatible `/chat/completions` endpoint. Compatible
providers can be configured without changing gateway contracts. No provider or
model is selected by default; missing credentials and model configuration fail closed.

## Python usage

```python
from aegis_ai import (
    AISettings, EvidenceItem, ModelGateway, SpecialistKind,
    SpecialistOrchestrator, SpecialistRequest,
)
from aegis_ai.providers.openai_compatible import OpenAICompatibleProvider

settings = AISettings.from_environment()
provider = OpenAICompatibleProvider(settings)
orchestrator = SpecialistOrchestrator(ModelGateway(provider))
request = SpecialistRequest(
    kind=SpecialistKind.ALERT_TRIAGE,
    tenant_id="server-resolved-tenant-id",
    request_id="server-generated-request-id",
    evidence=(EvidenceItem("alert-123", "siem_alert", "Synthetic alert evidence."),),
)
analysis = await orchestrator.analyze(request)
print(analysis.generation.text)
await provider.aclose()
```

## Security boundaries

- Tenant and request identifiers must be derived by the trusted calling backend,
  never untrusted client claims. They are not sent as model prompt content.
- Evidence must be loaded by a tenant-scoped backend query before constructing
  a specialist request; this package does not query customer stores.
- Evidence count, per-item size, aggregate size and analyst context are bounded.
- Evidence is serialized as data and explicitly treated as untrusted input.
- Outputs include evidence provenance and always require human review.
- There is no action interface, tool execution, cross-agent delegation, or
  autonomous remediation.
- Provider credentials are excluded from settings representations.
- Provider errors do not expose response bodies or authorization headers.
- Request and response bodies are not logged by this package.
- Do not send customer data to a provider until contractual, residency, privacy
  and tenant-isolation requirements have been reviewed and approved.
