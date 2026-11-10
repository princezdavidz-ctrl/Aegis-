"""Tests for the OpenAI-compatible embedding adapter."""

import json

import httpx
import pytest

from aegis_ai.knowledge.embeddings import (
    EmbeddingProviderError,
    OpenAICompatibleEmbedder,
)


def make_embedder(handler, dimensions=3):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    embedder = OpenAICompatibleEmbedder(
        base_url="https://embeddings.example/v1",
        model="security-embed-v1",
        api_key="test-secret",
        dimensions=dimensions,
        client=client,
    )
    return embedder, client


@pytest.mark.asyncio
async def test_embeddings_are_returned_in_input_order():
    def handler(request):
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-secret"
        payload = json.loads(request.content)
        assert payload["input"] == ["first", "second"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                ]
            },
        )

    embedder, client = make_embedder(handler)
    try:
        result = await embedder.embed(["first", "second"])
        assert result == ((0.1, 0.2, 0.3), (0.4, 0.5, 0.6))
        assert embedder.dimensions == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_provider_dimension_mismatch():
    embedder, client = make_embedder(
        lambda request: httpx.Response(
            200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]}
        )
    )
    try:
        with pytest.raises(EmbeddingProviderError, match="invalid response"):
            await embedder.embed(["one"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_duplicate_embedding_indices():
    embedder, client = make_embedder(
        lambda request: httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 0, "embedding": [0.4, 0.5, 0.6]},
                ]
            },
        ),
    )
    try:
        with pytest.raises(EmbeddingProviderError, match="invalid response"):
            await embedder.embed(["one", "two"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_non_finite_and_zero_vectors():
    for vector in ([0.0, 0.0, 0.0], [float("nan"), 0.2, 0.3]):
        embedder, client = make_embedder(
            lambda request, vector=vector: httpx.Response(
                200, json={"data": [{"index": 0, "embedding": vector}]}
            )
        )
        try:
            with pytest.raises(EmbeddingProviderError, match="invalid response"):
                await embedder.embed(["one"])
        finally:
            await client.aclose()


@pytest.mark.asyncio
async def test_provider_errors_do_not_leak_response_body():
    embedder, client = make_embedder(
        lambda request: httpx.Response(401, text="secret-token-should-not-appear")
    )
    try:
        with pytest.raises(EmbeddingProviderError) as error:
            await embedder.embed(["one"])
        assert "secret-token" not in str(error.value)
        assert "401" in str(error.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_unbounded_or_empty_batches_before_network():
    embedder, client = make_embedder(
        lambda request: httpx.Response(500, text="should not be called")
    )
    try:
        with pytest.raises(ValueError):
            await embedder.embed([])
        with pytest.raises(ValueError):
            await embedder.embed([" "])
    finally:
        await client.aclose()
