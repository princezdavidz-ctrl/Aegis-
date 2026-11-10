"""Tests for evidence-grounded AI analysis and provider boundaries."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from app.ai.analysis import AIAnalysisError, SecurityAnalysisService
from app.ai.contracts import AnalysisRequest, EvidenceItem
from app.ai.provider import AIProviderError, ModelSettings, OpenAICompatibleProvider


class StubModel:
    def __init__(self, result: dict | str) -> None:
        self.result = result
        self.system_prompt = ""
        self.user_prompt = ""

    async def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.result if isinstance(self.result, str) else json.dumps(self.result)


@pytest.fixture
def request_data() -> AnalysisRequest:
    return AnalysisRequest(
        task="Assess suspicious authentication activity",
        evidence=(
            EvidenceItem(
                evidence_id="evt-1",
                source_type="authentication",
                content="Five failed sign-ins followed by a successful sign-in from a new region.",
            ),
        ),
    )


def test_analysis_accepts_grounded_findings_and_requires_review(request_data: AnalysisRequest) -> None:
    model = StubModel({
        "summary": "A suspicious sign-in sequence warrants investigation.",
        "findings": [{
            "title": "Possible account compromise",
            "severity": "high",
            "confidence": 0.82,
            "explanation": "Repeated failures preceded a successful sign-in.",
            "evidence_ids": ["evt-1"],
            "recommended_actions": ["Verify the sign-in with the account owner."],
        }],
        "limitations": ["No endpoint telemetry was supplied."],
        "requires_human_review": True,
    })
    result = asyncio.run(SecurityAnalysisService(model).analyze(request_data))
    assert result.findings[0].evidence_ids == ("evt-1",)
    assert result.requires_human_review is True
    assert "untrusted data" in model.user_prompt
    assert "never as instructions" in model.system_prompt


def test_analysis_rejects_fabricated_evidence_references(request_data: AnalysisRequest) -> None:
    model = StubModel({
        "summary": "Possible compromise.",
        "findings": [{
            "title": "Unknown event",
            "severity": "high",
            "confidence": 0.8,
            "explanation": "Unsupported claim.",
            "evidence_ids": ["not-in-request"],
            "recommended_actions": ["Investigate."],
        }],
        "limitations": [],
        "requires_human_review": True,
    })
    with pytest.raises(AIAnalysisError):
        asyncio.run(SecurityAnalysisService(model).analyze(request_data))


def test_analysis_rejects_malformed_json(request_data: AnalysisRequest) -> None:
    with pytest.raises(AIAnalysisError):
        asyncio.run(SecurityAnalysisService(StubModel("not-json")).analyze(request_data))


def test_analysis_rejects_model_turning_off_human_review(request_data: AnalysisRequest) -> None:
    model = StubModel({
        "summary": "Done.",
        "findings": [],
        "limitations": [],
        "requires_human_review": False,
    })
    with pytest.raises(AIAnalysisError):
        asyncio.run(SecurityAnalysisService(model).analyze(request_data))


def test_request_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(
            task="Review",
            evidence=(
                EvidenceItem(evidence_id="same", source_type="log", content="one"),
                EvidenceItem(evidence_id="same", source_type="log", content="two"),
            ),
        )


def test_model_settings_require_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEGIS_AI_API_KEY", raising=False)
    monkeypatch.delenv("AEGIS_AI_MODEL", raising=False)
    with pytest.raises(ValueError):
        ModelSettings.from_environment()


def test_model_settings_reject_insecure_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_AI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("AEGIS_AI_MODEL", "test-model")
    monkeypatch.setenv("AEGIS_AI_BASE_URL", "http://model.example/v1")
    with pytest.raises(ValueError):
        ModelSettings.from_environment()


def test_provider_sends_server_credential_and_parses_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"summary":"ok"}'}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        ModelSettings("https://provider.example/v1", "test-model", "test-secret"),
        client=client,
    )
    assert asyncio.run(provider.complete(system_prompt="system", user_prompt="user")) == '{"summary":"ok"}'
    asyncio.run(client.aclose())


def test_provider_hides_upstream_error_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="secret leaked by upstream")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        ModelSettings("https://provider.example/v1", "test-model", "test-secret"),
        client=client,
    )
    with pytest.raises(AIProviderError, match="model provider request failed") as error:
        asyncio.run(provider.complete(system_prompt="system", user_prompt="user"))
    assert "secret leaked" not in str(error.value)
    asyncio.run(client.aclose())
