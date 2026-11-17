"""Embedding provider contract and safe OpenAI-compatible implementation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlsplit

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
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key is required")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model is required")
        if (
            isinstance(dimensions, bool)
            or not isinstance(dimensions, int)
            or not 1 <= dimensions <= 16_384
        ):
            raise ValueError("dimensions must be between 1 and 16384")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or not 1 <= timeout_seconds <= 120
        ):
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not isinstance(base_url, str):
            raise TypeError("base_url must be a string")

        try:
            parsed_url = urlsplit(base_url)
            hostname = parsed_url.hostname
            # Accessing .port also validates malformed/out-of-range port values.
            _ = parsed_url.port
        except ValueError:
            raise ValueError("base_url must be a valid HTTPS URL") from None

        is_https = parsed_url.scheme.lower() == "https"
        is_loopback_http = (
            parsed_url.scheme.lower() == "http"
            and hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if (
            not hostname
            or not (is_https or is_loopback_http)
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("base_url must use HTTPS outside localhost")

        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._model = model
        self._api_key = api_key
        self._dimensions = dimensions
        self._timeout = float(timeout_seconds)
        self._client = client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Embed 1–64 non-empty strings and preserve input order."""
        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise TypeError("embedding input must be a sequence of text strings")

        batch = tuple(texts)
        if not 1 <= len(batch) <= 64:
            raise ValueError("embedding batch must contain 1–64 texts")
        if any(
            not isinstance(text, str) or not text.strip() or len(text) > 20_000
            for text in batch
        ):
            raise ValueError("each embedding input must contain 1–20000 characters")

        payload = {
            "model": self._model,
            "input": list(batch),
            "dimensions": self._dimensions,
            "encoding_format": "float",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            if self._client is not None:
                response = await self._client.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                    follow_redirects=False,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        self._endpoint,
                        json=payload,
                        headers=headers,
                        follow_redirects=False,
                    )
        except httpx.HTTPError:
            raise EmbeddingProviderError("embedding provider request failed") from None

        if response.is_error:
            raise EmbeddingProviderError(
                f"embedding provider returned HTTP {response.status_code}"
            )

        try:
            body = response.json()
            if not isinstance(body, dict):
                raise TypeError("invalid response object")
            data = body.get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise ValueError("embedding count mismatch")

            ordered: list[tuple[float, ...] | None] = [None] * len(batch)
            for item in data:
                if not isinstance(item, dict):
                    raise TypeError("invalid embedding item")
                index = item.get("index")
                vector = item.get("embedding")
                if isinstance(index, bool) or not isinstance(index, int):
                    raise TypeError("invalid embedding index")
                if not 0 <= index < len(batch):
                    raise ValueError("invalid embedding index")
                if ordered[index] is not None:
                    raise ValueError("duplicate embedding index")
                if not isinstance(vector, list) or len(vector) != self._dimensions:
                    raise ValueError("embedding dimensions mismatch")
                if any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    for value in vector
                ):
                    raise ValueError("embedding values must be numeric")
                values = tuple(float(value) for value in vector)
                if any(not math.isfinite(value) for value in values):
                    raise ValueError("embedding contains a non-finite value")
                if not any(value != 0.0 for value in values):
                    raise ValueError("embedding vector cannot be all zero")
                ordered[index] = values

            if any(vector is None for vector in ordered):
                raise ValueError("missing embedding index")
            return tuple(vector for vector in ordered if vector is not None)
        except (KeyError, TypeError, ValueError, IndexError, OverflowError):
            raise EmbeddingProviderError(
                "embedding provider returned an invalid response"
            ) from None
