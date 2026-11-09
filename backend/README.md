# AEGIS FastAPI backend

The backend provides authenticated, tenant-scoped API boundaries. PostgreSQL
membership resolution and row-level security remain authoritative for tenant
access. AI analysis is advisory-only and requires a verified principal, an
active tenant membership, the `investigation:create` permission, and a durable
audit store.

## Install

From the repository root:

```bash
python -m pip install -e services/ai
python -m pip install -r backend/requirements-dev.txt
```

For a Render service whose Root Directory is `backend`, use this Build Command:

```bash
python -m pip install -e ../services/ai && python -m pip install -r requirements.txt
```

## AI provider configuration

Set these environment variables on the backend service to enable the shared
specialist runtime:

- `AEGIS_AI_PROVIDER` — provider label (defaults to `openai-compatible`)
- `AEGIS_AI_BASE_URL` — OpenAI-compatible API base URL (defaults to the OpenAI API)
- `AEGIS_AI_MODEL` — model identifier; must be explicitly configured
- `AEGIS_AI_API_KEY` — provider credential, stored only in the deployment secret manager
- `AEGIS_AI_TIMEOUT_SECONDS` — request timeout from 1 to 120 seconds
- `AEGIS_AI_MAX_OUTPUT_TOKENS` — output token cap from 1 to 8192

The AI runtime stays disabled when the model or API key is absent. The API returns
503 rather than substituting a mock model. Never commit credentials or put them
in customer prompts or logs.

The provider is called only after authentication, tenant membership resolution,
authorization and input validation. Customer data is sent to the configured
provider only when the operator has intentionally configured that provider.
Review the provider's data-processing and retention terms before production use.

No tool execution, autonomous remediation, patch deployment, or production
change is enabled by this integration.
