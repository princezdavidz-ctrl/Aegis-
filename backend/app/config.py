"""Validated, environment-driven application configuration."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Environment = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseModel):
    """Validated settings; secret values are excluded from representations."""

    model_config = ConfigDict(frozen=True)

    app_name: str = Field(default="AEGIS API", min_length=1, max_length=80)
    environment: Environment = "development"
    log_level: LogLevel = "INFO"
    database_url: SecretStr | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    oidc_jwks_cache_seconds: int = Field(default=300, ge=30, le=600)

    @field_validator("app_name")
    @classmethod
    def normalize_app_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("app_name must contain a non-whitespace character")
        return normalized

    @model_validator(mode="after")
    def validate_oidc_configuration(self) -> Settings:
        configured = (
            self.oidc_issuer is not None,
            self.oidc_audience is not None,
            self.oidc_jwks_url is not None,
        )
        if any(configured) and not all(configured):
            raise ValueError("OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL must be configured together")
        return self

    @classmethod
    def from_environment(cls) -> Settings:
        """Load documented settings; never log environment values."""

        values: dict[str, str] = {
            "app_name": os.getenv("AEGIS_APP_NAME", "AEGIS API"),
            "environment": os.getenv("AEGIS_ENVIRONMENT", "development"),
            "log_level": os.getenv("AEGIS_LOG_LEVEL", "INFO"),
            "oidc_clock_skew_seconds": os.getenv("AEGIS_OIDC_CLOCK_SKEW_SECONDS", "30"),
            "oidc_jwks_cache_seconds": os.getenv("AEGIS_OIDC_JWKS_CACHE_SECONDS", "300"),
        }
        for setting, variable in (
            ("database_url", "AEGIS_DATABASE_URL"),
            ("oidc_issuer", "AEGIS_OIDC_ISSUER"),
            ("oidc_audience", "AEGIS_OIDC_AUDIENCE"),
            ("oidc_jwks_url", "AEGIS_OIDC_JWKS_URL"),
        ):
            value = os.getenv(variable)
            if value:
                values[setting] = value
        return cls.model_validate(values)
