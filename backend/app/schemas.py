"""Typed response contracts for service health endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.config import Environment


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["alive"] = "alive"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    service: str
    environment: Environment
    checks: dict[str, Literal["ready", "not_configured"]]
