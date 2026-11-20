"""Fail-closed configuration for the tenant-scoped knowledge memory adapter."""

from __future__ import annotations

import os
from typing import ClassVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.config import Environment


class KnowledgeSettings(BaseModel):
    """Optional knowledge-memory settings; partial configuration is rejected.

    The feature is disabled when none of its required settings are supplied.
    Once any core setting is present, every database and embedding setting is
    required so a partially configured service cannot silently use a weaker
    fallback. Credentials are secret-wrapped and excluded from representations.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    _CONFIGURATION_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "runtime_database_url",
            "ingestor_database_url",
            "embedding_provider",
            "embedding_base_url",
            "embedding_model",
            "embedding_model_revision",
            "embedding_dimensions",
            "embedding_api_key",
        }
    )
    _REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "runtime_database_url",
        "ingestor_database_url",
        "embedding_model",
        "embedding_model_revision",
        "embedding_dimensions",
        "embedding_api_key",
    )

    environment: Environment = "development"
    runtime_database_url: SecretStr | None = Field(default=None, repr=False)
    ingestor_database_url: SecretStr | None = Field(default=None, repr=False)
    embedding_provider: str = Field(default="openai-compatible", min_length=1, max_length=80)
    embedding_base_url: str = Field(
        default="https://api.openai.com/v1",
        min_length=1,
        max_length=500,
    )
    embedding_model: str | None = Field(default=None, min_length=1, max_length=160)
    embedding_model_revision: str | None = Field(default=None, min_length=1, max_length=120)
    embedding_dimensions: int | None = Field(default=None, ge=1, le=16_000)
    embedding_api_key: SecretStr | None = Field(default=None, repr=False)
    embedding_timeout_seconds: int = Field(default=30, ge=1, le=120)

    @field_validator("runtime_database_url", "ingestor_database_url", "embedding_api_key")
    @classmethod
    def validate_nonempty_secrets(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("configured secret values must not be empty")
        return value

    @field_validator("embedding_provider", "embedding_model", "embedding_model_revision")
    @classmethod
    def normalize_profile_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("embedding profile values must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_memory_configuration(self) -> KnowledgeSettings:
        supplied = self.model_fields_set.intersection(self._CONFIGURATION_FIELDS)
        if not supplied:
            return self

        missing = [
            name
            for name in self._REQUIRED_FIELDS
            if getattr(self, name) is None
        ]
        if missing:
            raise ValueError(
                "knowledge memory configuration is incomplete; missing: "
                + ", ".join(missing)
            )

        self._validate_database_role(
            self.runtime_database_url,
            expected_role="aegis_runtime",
            setting_name="AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL",
        )
        self._validate_database_role(
            self.ingestor_database_url,
            expected_role="aegis_ingestor",
            setting_name="AEGIS_KNOWLEDGE_INGESTOR_DATABASE_URL",
        )
        self._validate_embedding_url()
        return self

    @staticmethod
    def _validate_database_role(
        secret_url: SecretStr | None,
        *,
        expected_role: str,
        setting_name: str,
    ) -> None:
        assert secret_url is not None
        try:
            parsed = make_url(secret_url.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError(f"{setting_name} must be a valid PostgreSQL URL") from None

        if (
            parsed.drivername != "postgresql+asyncpg"
            or not parsed.host
            or not parsed.database
            or parsed.username != expected_role
            or parsed.password is None
        ):
            raise ValueError(
                f"{setting_name} must use postgresql+asyncpg and the {expected_role} role"
            )

    def _validate_embedding_url(self) -> None:
        try:
            parsed = urlsplit(self.embedding_base_url)
            hostname = parsed.hostname
            _ = parsed.port
        except ValueError:
            raise ValueError("embedding_base_url must be a valid HTTPS URL") from None

        is_https = parsed.scheme.lower() == "https"
        is_loopback_http = (
            self.environment in {"development", "test"}
            and parsed.scheme.lower() == "http"
            and hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if (
            not hostname
            or not (is_https or is_loopback_http)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "embedding_base_url must use HTTPS; loopback HTTP is allowed only in development/test"
            )

    @property
    def enabled(self) -> bool:
        """Whether the complete database and embedding configuration is present."""

        return all(getattr(self, name) is not None for name in self._REQUIRED_FIELDS)

    @classmethod
    def from_environment(
        cls,
        *,
        environment: Environment = "development",
    ) -> KnowledgeSettings:
        """Load only the documented memory settings without exposing credentials."""

        values: dict[str, object] = {"environment": environment}
        variables = {
            "runtime_database_url": "AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL",
            "ingestor_database_url": "AEGIS_KNOWLEDGE_INGESTOR_DATABASE_URL",
            "embedding_provider": "AEGIS_KNOWLEDGE_EMBEDDING_PROVIDER",
            "embedding_base_url": "AEGIS_KNOWLEDGE_EMBEDDING_BASE_URL",
            "embedding_model": "AEGIS_KNOWLEDGE_EMBEDDING_MODEL",
            "embedding_model_revision": "AEGIS_KNOWLEDGE_EMBEDDING_REVISION",
            "embedding_dimensions": "AEGIS_KNOWLEDGE_EMBEDDING_DIMENSIONS",
            "embedding_api_key": "AEGIS_KNOWLEDGE_EMBEDDING_API_KEY",
            "embedding_timeout_seconds": "AEGIS_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS",
        }
        for setting_name, variable_name in variables.items():
            value = os.getenv(variable_name)
            if value is not None:
                values[setting_name] = value
        return cls.model_validate(values)
