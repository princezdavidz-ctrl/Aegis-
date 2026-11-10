"""Trusted identity and narrowly scoped permission value objects."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrincipalType(StrEnum):
    USER = "user"
    SERVICE = "service"


class Permission(StrEnum):
    """Explicit capabilities; there is intentionally no wildcard permission."""

    INVESTIGATION_READ = "investigation:read"
    INVESTIGATION_CREATE = "investigation:create"
    TELEMETRY_READ = "telemetry:read"
    TOOL_EXECUTE = "tool:execute"
    TENANT_PROVISION = "tenant:provision"


class Principal(BaseModel):
    """Immutable identity assertion from a trusted authentication boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(min_length=1, max_length=128)
    principal_type: PrincipalType
    scopes: frozenset[Permission] = frozenset()

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 or ord(character) == 127 for character in normalized):
            raise ValueError("subject must be a non-empty opaque identifier without control characters")
        return normalized
