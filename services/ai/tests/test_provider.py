from __future__ import annotations
import json
import httpx
import pytest
from aegis_ai.config import AISettings
from aegis_ai.contracts import GenerationRequest
from aegis_ai.providers.openai_compatible import OpenAICompatibleProvider, ProviderError

def make_request() -> GenerationRequest:
    return GenerationRequest("Advisory analyst.", "Synthetic alert.", "tenant-1", "request-1", 300)

@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_response() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer test-secret"
        body = json.loads(req.content)
        assert body["model"] == "test-model" and body["max_tokens"] == 300
        return httpx.Response(200, json={"choices":[{"message":{"content":"Evidence-based assessment."},
            "finish_reason":"stop"}],"usage":{"prompt_tokens":12,"completion_tokens":7}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(AISettings(base_url="https://provider.example/v1",
        model="test-model", api_key="test-secret"), client=client)
    result = await provider.generate(make_request())
    assert result.text == "Evidence-based assessment."
    assert result.input_tokens == 12
    await client.aclose()

@pytest.mark.asyncio
async def test_provider_failure_does_not_leak_response_body() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(500, text="private provider internals")))
    provider = OpenAICompatibleProvider(AISettings(base_url="https://provider.example/v1",
        model="test", api_key="secret"), client=client)
    with pytest.raises(ProviderError) as error:
        await provider.generate(make_request())
    assert "private provider internals" not in str(error.value)
    assert "secret" not in str(error.value)
    await client.aclose()

@pytest.mark.asyncio
async def test_missing_credentials_fail_closed() -> None:
    provider = OpenAICompatibleProvider(AISettings(base_url="https://provider.example/v1",
        model="test"))
    with pytest.raises(ProviderError, match="credentials"):
        await provider.generate(make_request())
    await provider.aclose()

def test_settings_reject_insecure_remote_provider() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AISettings(base_url="http://provider.example/v1", model="test")
