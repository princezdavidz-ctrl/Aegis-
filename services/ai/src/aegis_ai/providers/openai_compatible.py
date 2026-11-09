"""HTTP adapter for OpenAI-compatible chat-completions endpoints."""
from __future__ import annotations
import httpx
from aegis_ai.config import AISettings
from aegis_ai.contracts import GenerationRequest, GenerationResult

class ProviderError(RuntimeError):
    """Safe provider error; deliberately excludes response bodies and secrets."""

class OpenAICompatibleProvider:
    """Interoperate with compatible services using a small HTTP surface."""
    def __init__(self, settings: AISettings, *, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.name = settings.provider
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=settings.timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if self.settings.model == "unset":
            raise ProviderError("AI model is not configured")
        if not self.settings.api_key:
            raise ProviderError("AI provider credentials are not configured")
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                {"role": "user", "content": request.user_input},
            ],
            "max_tokens": min(request.max_output_tokens, self.settings.max_output_tokens),
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "X-AEGIS-Request-ID": request.request_id,
        }
        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ProviderError("AI provider returned an empty response")
            usage = data.get("usage") or {}
            return GenerationResult(
                text=content, provider=self.settings.provider, model=self.settings.model,
                finish_reason=choice.get("finish_reason"),
                input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
            )
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("AI provider request failed or returned an invalid response") from None
