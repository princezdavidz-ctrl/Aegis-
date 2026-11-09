"""Provider interface shared by interchangeable model adapters."""

from __future__ import annotations

from typing import Protocol

from aegis_ai.contracts import GenerationRequest, GenerationResult


class ModelProvider(Protocol):
    name: str

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a response without exposing provider-specific SDK types."""
