"""OpenAI-compatible chat-completions gateway with strict failure handling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx


class AIProviderError(RuntimeError):
    """A safe, provider-neutral model gateway failure."""


@dataclass(frozen=True)
class ModelSettings:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0
    max_output_tokens: int = 1800

    @classmethod
    def from_environment(cls) -> ModelSettings:
        """Load credentials only from process environment, never from requests."""

        base_url = os.getenv("AEGIS_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("AEGIS_AI_MODEL", "").strip()
        api_key = os.getenv("AEGIS_AI_API_KEY", "")
        if not model:
            raise ValueError("AEGIS_AI_MODEL must be configured")
        if not api_key:
            raise ValueError("AEGIS_AI_API_KEY must be configured")
        parsed = httpx.URL(base_url)
        if parsed.scheme != "https" or not parsed.host or parsed.username or parsed.password:
            raise ValueError("AEGIS_AI_BASE_URL must be an HTTPS URL without embedded credentials")
        return cls(base_url=base_url, model=model, api_key=api_key)


class ChatModel(Protocol):
    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return model text; callers must treat it as untrusted."""
        ...


class OpenAICompatibleProvider:
    """Minimal provider adapter; no tools, streaming, or side effects are enabled."""

    def __init__(
        self,
        settings: ModelSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._settings.timeout_seconds)
        try:
            response = await client.post(
                f"{self._settings.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._settings.api_key}"},
                json={
                    "model": self._settings.model,
                    "temperature": 0,
                    "max_tokens": self._settings.max_output_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise AIProviderError("model returned empty content")
            if len(content) > 24000:
                raise AIProviderError("model response exceeded the configured size limit")
            return content
        except AIProviderError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            # Do not expose provider response bodies, credentials, or customer data.
            raise AIProviderError("model provider request failed") from None
        finally:
            if owns_client:
                await client.aclose()
