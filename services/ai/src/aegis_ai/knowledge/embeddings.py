"""Embedding provider contract and safe OpenAI-compatible implementation."""

from __future__ import annotations

import math
from typing import Protocol, Sequence

import httpx


class EmbeddingProvider(Protocol):
    """Converts bounded text batches into fixed-width dense vectors."""

    @property
    def dimensions(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


class EmbeddingProviderError(RuntimeError):
    """A sanitized provider or response validation failure."""


class OpenAICompatibleEmbedder:
    """Embeddings API client; credentials are supplied at runtime, never persisted."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        dimensions: int,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        if not model.strip():
            raise ValueError("model is required")
        if not 1 <= dimensions <= 16_384:
            raise ValueError("dimensions must be between 1 and 16384")
        if not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("base_url must use HTTPS outside localhost")
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._model = model
        self._api_key = api_key
        self._dimensions = dimensions
        self._timeout = timeout_seconds
        self._client = client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Embed 1–64 non-empty strings and preserve input order."""
        if not 1 <= len(texts) <= 64:
            raise ValueError("embedding batch must contain 1–64 texts")
        if any(not text.strip() or len(text) > 20_000 for text in texts):
            raise ValueError("each embedding input must contain 1–20000 characters")

        payload = {
            "model": self._model,
            "input": list(texts),
            "dimensions": self._dimensions,
            "encoding_format": "float",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._client is not None:
            response = await self._client.post(
                self._endpoint, json=payload, headers=headers, timeout=self._timeout
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._endpoint, json=payload, headers=headers)

        if response.is_error:
            raise EmbeddingProviderError(
                f"embedding provider returned HTTP {response.status_code}"
            )
        try:
            data = response.json()["data"]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError("embedding count mismatch")
            ordered: list[tuple[float, ...] | None] = [None] * len(texts)
            for item in data:
                index = item["index"]
                vector = item["embedding"]
                if not isinstance(index, int) or not 0 <= index < len(texts):
                    raise ValueError("invalid embedding index")
                if ordered[index] is not None:
                    raise ValueError("duplicate embedding index")
                if not isinstance(vector, list) or len(vector) != self._dimensions:
                    raise ValueError("embedding dimensions mismatch")
                values = tuple(float(value) for value in vector)
                if any(not math.isfinite(value) for value in values):
                    raise ValueError("embedding contains a non-finite value")
                if not any(value != 0.0 for value in values):
                    raise ValueError("embedding vector cannot be all zero")
                ordered[index] = values
            if any(vector is None for vector in ordered):
                raise ValueError("missing embedding index")
            return tuple(vector for vector in ordered if vector is not None)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise EmbeddingProviderError("embedding provider returned an invalid response") from exc
