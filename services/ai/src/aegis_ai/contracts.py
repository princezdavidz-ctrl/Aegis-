"""Typed model gateway contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One bounded advisory generation request."""

    system_instruction: str
    user_input: str
    tenant_id: str
    request_id: str
    max_output_tokens: int = 1200

    def __post_init__(self) -> None:
        if not self.system_instruction.strip() or not self.user_input.strip():
            raise ValueError("system_instruction and user_input must not be empty")
        if not self.tenant_id.strip() or not self.request_id.strip():
            raise ValueError("tenant_id and request_id are required")
        if len(self.user_input) > 40_000:
            raise ValueError("user_input exceeds the 40000-character limit")
        if not 1 <= self.max_output_tokens <= 8192:
            raise ValueError("max_output_tokens must be between 1 and 8192")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    finish_reason: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    status: Literal["completed"] = "completed"
