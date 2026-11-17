"""Tests for the OpenAI-compatible embedding adapter."""

import json
import math

import httpx
import pytest

from aegis_ai.knowledge.embeddings import (
    EmbeddingProviderError,
    OpenAICompatibleEmbedder,
)


def make_embedder(handler, dimensions=3, *, base_url="https://embeddings.example/v1"):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    embedder = OpenAICompatibleEmbedder(
        base_url=base_url,
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
@pytest.mark.parametrize(
    "vector",
    [
        [0.0, 0.0, 0.0],
        [math.nan, 0.2, 0.3],
        [math.inf, 0.2, 0.3],
        [-math.inf, 0.2, 0.3],
    ],
)
async def test_rejects_non_finite_and_zero_vectors(vector):
    def handler(request):
        # Python's JSON encoder emits the non-standard NaN/Infinity tokens so
        # the adapter's finite-number validation is exercised on raw responses.
        content = json.dumps(
            {"data": [{"index": 0, "embedding": vector}]},
            allow_nan=True,
        )
        return httpx.Response(
            200,
            content=content.encode(),
            headers={"content-type": "application/json"},
        )

    embedder, client = make_embedder(handler)
    try:
        with pytest.raises(EmbeddingProviderError, match="invalid response"):
            await embedder.embed(["one"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_non_numeric_and_boolean_embedding_values():
    for vector in ([0.1, "0.2", 0.3], [0.1, True, 0.3]):
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
async def test_rejects_invalid_embedding_indices():
    for index in (True, -1, 1):
        embedder, client = make_embedder(
            lambda request, index=index: httpx.Response(
                200,
                json={
                    "data": [
                        {"index": index, "embedding": [0.1, 0.2, 0.3]}
                    ]
                },
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
async def test_transport_errors_are_sanitized():
    def handler(request):
        raise httpx.ConnectError("secret transport details", request=request)

    embedder, client = make_embedder(handler)
    try:
        with pytest.raises(EmbeddingProviderError) as error:
            await embedder.embed(["one"])
        assert str(error.value) == "embedding provider request failed"
        assert "secret transport details" not in str(error.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rejects_unbounded_or_invalid_batches_before_network():
    embedder, client = make_embedder(
        lambda request: httpx.Response(500, text="should not be called")
    )
    try:
        invalid_batches = (
            ([], ValueError),
            ([" "], ValueError),
            (["x" * 20_001], ValueError),
            ([None], ValueError),
            ("not-a-batch", TypeError),
            ([str(index) for index in range(65)], ValueError),
        )
        for batch, error_type in invalid_batches:
            with pytest.raises(error_type):
                await embedder.embed(batch)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://embeddings.example/v1",
        "http://localhost.evil.example/v1",
        "http://127.0.0.1.evil.example/v1",
        "https://user:password@embeddings.example/v1",
        "https://embeddings.example/v1?token=unexpected",
        "https://embeddings.example/v1#fragment",
        "https:///missing-host",
    ],
)
def test_rejects_unsafe_or_malformed_provider_urls(base_url):
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleEmbedder(
            base_url=base_url,
            model="security-embed-v1",
            api_key="test-secret",
            dimensions=3,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://embeddings.example/v1",
        "http://localhost:8080/v1",
        "http://127.0.0.1:8080/v1",
        "http://[::1]:8080/v1",
    ],
)
def test_accepts_https_and_exact_loopback_development_urls(base_url):
    embedder = OpenAICompatibleEmbedder(
        base_url=base_url,
        model="security-embed-v1",
        api_key="test-secret",
        dimensions=3,
    )
    assert embedder.dimensions == 3
