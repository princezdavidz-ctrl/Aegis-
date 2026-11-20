"""Tests for fail-closed persistent knowledge-memory configuration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.ai.knowledge_config import KnowledgeSettings
from pydantic import ValidationError


def _complete_environment() -> dict[str, str]:
    return {
        "AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL": (
            "postgresql+asyncpg://aegis_runtime:runtime-password@db.example/aegis"
        ),
        "AEGIS_KNOWLEDGE_INGESTOR_DATABASE_URL": (
            "postgresql+asyncpg://aegis_ingestor:ingestor-password@db.example/aegis"
        ),
        "AEGIS_KNOWLEDGE_EMBEDDING_PROVIDER": "openai-compatible",
        "AEGIS_KNOWLEDGE_EMBEDDING_BASE_URL": "https://embeddings.example/v1",
        "AEGIS_KNOWLEDGE_EMBEDDING_MODEL": "security-embed",
        "AEGIS_KNOWLEDGE_EMBEDDING_REVISION": "2026-11-01",
        "AEGIS_KNOWLEDGE_EMBEDDING_DIMENSIONS": "1536",
        "AEGIS_KNOWLEDGE_EMBEDDING_API_KEY": "embedding-secret-value",
        "AEGIS_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS": "45",
    }


def test_memory_is_disabled_when_no_memory_settings_are_supplied() -> None:
    with patch.dict("os.environ", {}, clear=True):
        settings = KnowledgeSettings.from_environment(environment="staging")

    assert settings.enabled is False
    assert settings.runtime_database_url is None
    assert settings.ingestor_database_url is None
    assert settings.embedding_model is None


def test_complete_memory_configuration_loads_separate_roles_and_profile() -> None:
    values = _complete_environment()
    with patch.dict("os.environ", values, clear=True):
        settings = KnowledgeSettings.from_environment(environment="staging")

    assert settings.enabled is True
    assert settings.runtime_database_url is not None
    assert settings.runtime_database_url.get_secret_value() == values[
        "AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL"
    ]
    assert settings.ingestor_database_url is not None
    assert settings.ingestor_database_url.get_secret_value() == values[
        "AEGIS_KNOWLEDGE_INGESTOR_DATABASE_URL"
    ]
    assert settings.embedding_provider == "openai-compatible"
    assert settings.embedding_model == "security-embed"
    assert settings.embedding_model_revision == "2026-11-01"
    assert settings.embedding_dimensions == 1536
    assert settings.embedding_timeout_seconds == 45


def test_memory_credentials_are_not_in_settings_representation() -> None:
    values = _complete_environment()
    with patch.dict("os.environ", values, clear=True):
        settings = KnowledgeSettings.from_environment(environment="staging")

    rendered = repr(settings)
    assert "runtime-password" not in rendered
    assert "ingestor-password" not in rendered
    assert "embedding-secret-value" not in rendered


@pytest.mark.parametrize(
    "environment",
    [
        {
            "AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL": (
                "postgresql+asyncpg://aegis_runtime:runtime-password@db.example/aegis"
            )
        },
        {
            "AEGIS_KNOWLEDGE_EMBEDDING_MODEL": "security-embed",
            "AEGIS_KNOWLEDGE_EMBEDDING_API_KEY": "embedding-secret-value",
        },
    ],
)
def test_partial_memory_configuration_is_rejected(environment: dict[str, str]) -> None:
    with (
        patch.dict("os.environ", environment, clear=True),
        pytest.raises(ValidationError, match="knowledge memory configuration is incomplete"),
    ):
        KnowledgeSettings.from_environment(environment="staging")


def test_runtime_and_ingestor_urls_must_use_distinct_expected_roles() -> None:
    values = _complete_environment()
    values["AEGIS_KNOWLEDGE_INGESTOR_DATABASE_URL"] = (
        "postgresql+asyncpg://aegis_runtime:another-password@db.example/aegis"
    )
    with (
        patch.dict("os.environ", values, clear=True),
        pytest.raises(ValidationError, match="aegis_ingestor role"),
    ):
        KnowledgeSettings.from_environment(environment="staging")


def test_memory_database_urls_must_use_postgresql_asyncpg() -> None:
    values = _complete_environment()
    values["AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL"] = "sqlite+aiosqlite:///./aegis.db"
    with (
        patch.dict("os.environ", values, clear=True),
        pytest.raises(ValidationError, match="aegis_runtime role"),
    ):
        KnowledgeSettings.from_environment(environment="staging")


def test_non_loopback_http_embedding_endpoint_is_rejected_outside_development() -> None:
    values = _complete_environment()
    values["AEGIS_KNOWLEDGE_EMBEDDING_BASE_URL"] = "http://embeddings.example/v1"
    with (
        patch.dict("os.environ", values, clear=True),
        pytest.raises(ValidationError, match="must use HTTPS"),
    ):
        KnowledgeSettings.from_environment(environment="staging")


def test_loopback_http_embedding_endpoint_is_allowed_in_development() -> None:
    values = _complete_environment()
    values["AEGIS_KNOWLEDGE_EMBEDDING_BASE_URL"] = "http://127.0.0.1:11434/v1"
    with patch.dict("os.environ", values, clear=True):
        settings = KnowledgeSettings.from_environment(environment="development")

    assert settings.enabled is True


def test_embedding_endpoint_rejects_embedded_credentials_and_query_strings() -> None:
    values = _complete_environment()
    values["AEGIS_KNOWLEDGE_EMBEDDING_BASE_URL"] = (
        "https://user:password@embeddings.example/v1?token=secret"
    )
    with (
        patch.dict("os.environ", values, clear=True),
        pytest.raises(ValidationError, match="must use HTTPS"),
    ):
        KnowledgeSettings.from_environment(environment="staging")


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("AEGIS_KNOWLEDGE_EMBEDDING_DIMENSIONS", "0"),
        ("AEGIS_KNOWLEDGE_EMBEDDING_DIMENSIONS", "16001"),
        ("AEGIS_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS", "0"),
        ("AEGIS_KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS", "121"),
    ],
)
def test_embedding_bounds_are_validated(setting: str, value: str) -> None:
    values = _complete_environment()
    values[setting] = value
    with (
        patch.dict("os.environ", values, clear=True),
        pytest.raises(ValidationError),
    ):
        KnowledgeSettings.from_environment(environment="staging")
