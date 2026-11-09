"""Provider-neutral AI gateway; deliberately exposes no tool-execution interface."""

from __future__ import annotations

from aegis_ai.contracts import GenerationRequest, GenerationResult
from aegis_ai.providers.base import ModelProvider


class ModelGateway:
    """Thin policy boundary around a configured model provider."""

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate advisory text; tenant and request context are mandatory."""
        return await self._provider.generate(request)
