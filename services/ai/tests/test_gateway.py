from __future__ import annotations

import asyncio

import pytest

from aegis_ai.contracts import GenerationRequest, GenerationResult
from aegis_ai.gateway import ModelGateway
from aegis_ai.safety import AEGIS_SYSTEM_POLICY, compose_system_instruction


class FakeProvider:
    name = "fake"

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        assert request.tenant_id == "tenant-a"
        return GenerationResult("Observed suspicious login.", self.name, "test-model", "stop")


def test_gateway_uses_provider_neutral_contract() -> None:
    request = GenerationRequest(
        compose_system_instruction("Analyze alert."),
        "Five failed logins.",
        "tenant-a",
        "req-1",
    )
    result = asyncio.run(ModelGateway(FakeProvider()).generate(request))
    assert result.provider == "fake"
    assert "suspicious login" in result.text


def test_system_policy_treats_evidence_as_untrusted() -> None:
    instruction = compose_system_instruction("Summarize incident.")
    assert instruction.startswith(AEGIS_SYSTEM_POLICY)
    assert "untrusted data" in instruction
    assert "human" in instruction


@pytest.mark.parametrize(
    "kwargs",
    [
        {"system_instruction": "", "user_input": "x", "tenant_id": "t", "request_id": "r"},
        {"system_instruction": "s", "user_input": "", "tenant_id": "t", "request_id": "r"},
        {"system_instruction": "s", "user_input": "x", "tenant_id": "", "request_id": "r"},
        {"system_instruction": "s", "user_input": "x", "tenant_id": "t", "request_id": ""},
        {"system_instruction": "s", "user_input": "x" * 40001, "tenant_id": "t", "request_id": "r"},
    ],
)
def test_invalid_requests_are_rejected(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        GenerationRequest(**kwargs)


def test_provider_policy_is_bounded() -> None:
    with pytest.raises(ValueError):
        GenerationRequest("s", "u", "t", "r", 9000)
