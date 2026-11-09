# AEGIS AI runtime

The first executable AI increment provides a provider-neutral model gateway and
an OpenAI-compatible HTTP adapter. It is advisory-only: there is no model
tool-calling surface, shell access, security-tool execution, patch deployment,
or autonomous remediation.

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
from aegis_ai import AISettings, GenerationRequest, ModelGateway
from aegis_ai.providers.openai_compatible import OpenAICompatibleProvider
from aegis_ai.safety import compose_system_instruction

settings = AISettings.from_environment()
provider = OpenAICompatibleProvider(settings)
gateway = ModelGateway(provider)
request = GenerationRequest(
    system_instruction=compose_system_instruction("Triage this defensive alert."),
    user_input="Synthetic alert evidence goes here.",
    tenant_id="server-resolved-tenant-id",
    request_id="server-generated-request-id",
)
result = await gateway.generate(request)
await provider.aclose()
```

## Security boundaries
- Tenant and request identifiers are required, but must be derived by the
  trusted calling backend, never untrusted client claims. They are not sent as
  model prompt content.
- Provider credentials are excluded from settings representations.
- Provider errors do not expose response bodies or authorization headers.
- Request and response bodies are not logged by this package.
- Input size, output tokens and network timeout are bounded.
- Evidence is treated as untrusted data in the fixed system policy.
- The policy is defense-in-depth, not a substitute for deterministic controls.
- Do not send customer data to a provider until contractual, residency, privacy
  and tenant-isolation requirements have been reviewed and approved.
