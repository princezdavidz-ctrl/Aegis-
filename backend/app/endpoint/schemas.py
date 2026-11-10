"""Versioned, tenant-agnostic endpoint telemetry envelope.

Tenant ownership is intentionally absent from the client payload. The ingestion
boundary must resolve the tenant from the authenticated device credential.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EndpointPlatform(StrEnum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class EndpointEventType(StrEnum):
    HEARTBEAT = "heartbeat"
    INVENTORY = "inventory"
    PROCESS = "process"
    SERVICE = "service"
    PACKAGE = "package"
    SECURITY_POSTURE = "security_posture"
    FILE_INTEGRITY = "file_integrity"
    OS_SECURITY_EVENT = "os_security_event"


class EndpointAgentDescriptor(BaseModel):
    """Non-secret metadata supplied during authenticated device enrollment."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_version: str = Field(min_length=1, max_length=32)
    platform: EndpointPlatform
    platform_version: str = Field(min_length=1, max_length=80)
    architecture: str = Field(min_length=1, max_length=32)
    hostname: str = Field(min_length=1, max_length=255)
    collection_profile: Literal["minimal", "standard", "extended"] = "standard"

    @field_validator("agent_version", "platform_version", "architecture", "hostname")
    @classmethod
    def reject_blank_or_control_characters(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("metadata must be non-empty and contain no control characters")
        return value


class EndpointTelemetryEnvelope(BaseModel):
    """Bounded event envelope; identity and tenant are established out of band."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    device_id: UUID
    event_id: UUID
    sequence: int = Field(ge=1, le=2**63 - 1)
    observed_at: datetime
    event_type: EndpointEventType
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def require_timezone_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("payload")
    @classmethod
    def bound_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must contain finite JSON values only") from exc
        if len(encoded.encode("utf-8")) > 32_768:
            raise ValueError("payload exceeds 32768-byte limit")
        return value