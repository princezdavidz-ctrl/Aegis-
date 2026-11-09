"""Validated, environment-driven application configuration."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

Environment = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseModel):
    """Validated settings; secret values are excluded from representations."""

    model_config = ConfigDict(frozen=True)

    app_name: str = Field(default="AEGIS API", min_length=1, max_length=80)
    environment: Environment = "development"
    log_level: LogLevel = "INFO"
    database_url: SecretStr | None = None

    @field_validator("app_name")
    @classmethod
    def normalize_app_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("app_name must contain a non-whitespace character")
        return normalized

    @classmethod
    def from_environment(cls) -> Settings:
        """Load documented settings; never log environment values."""

        values: dict[str, str] = {
            "app_name": os.getenv("AEGIS_APP_NAME", "AEGIS API"),
            "environment": os.getenv("AEGIS_ENVIRONMENT", "development"),
            "log_level": os.getenv("AEGIS_LOG_LEVEL", "INFO"),
        }
        database_url = os.getenv("AEGIS_DATABASE_URL")
        if database_url:
            values["database_url"] = database_url
        return cls.model_validate(values)
