"""FastAPI lifespan tests for the optional persistent knowledge runtime."""

from __future__ import annotations

from uuid import UUID

import app.ai.knowledge_runtime as knowledge_runtime_module
import app.main as main_module
import pytest
from app.config import Settings
from app.main import create_app
from app.security.tenant import TenantContext
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

_MEMORY_ENVIRONMENT = {
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
    "AEGIS_KNOWLEDGE_EMBEDDING_DIMENSIONS": "3",
    "AEGIS_KNOWLEDGE_EMBEDDING_API_KEY": "test-embedding-key",
}


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    def __init__(self, role: str, error: Exception | None = None) -> None:
        self.role = role
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalar(self, statement: object) -> str:
        assert str(statement) == "SELECT current_user"
        if self.error is not None:
            raise self.error
        return self.role


class FakeSessionFactory:
    def __init__(self, role: str, error: Exception | None = None) -> None:
        self.role = role
        self.error = error

    def __call__(self) -> FakeSession:
        return FakeSession(self.role, self.error)


class FakeEmbedder:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        dimensions: int,
        timeout_seconds: float,
    ) -> None:
        assert base_url == "https://embeddings.example/v1"
        assert model == "security-embed"
        assert api_key == "test-embedding-key"
        assert timeout_seconds == 30
        self.dimensions = dimensions


def _configure_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _MEMORY_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


def _install_fake_database(
    monkeypatch: pytest.MonkeyPatch,
    *,
    roles: dict[str, str] | None = None,
    errors: dict[str, Exception] | None = None,
) -> list[FakeEngine]:
    engines: list[FakeEngine] = []
    actual_roles = roles or {}
    connection_errors = errors or {}

    def create_factory(database_url: str) -> tuple[FakeEngine, FakeSessionFactory]:
        expected_role = (
            "aegis_runtime" if "aegis_runtime:" in database_url else "aegis_ingestor"
        )
        engine = FakeEngine()
        engines.append(engine)
        return (
            engine,
            FakeSessionFactory(
                actual_roles.get(expected_role, expected_role),
                connection_errors.get(expected_role),
            ),
        )

    monkeypatch.setattr(main_module, "create_session_factory", create_factory)
    monkeypatch.setattr(
        knowledge_runtime_module, "OpenAICompatibleEmbedder", FakeEmbedder
    )
    return engines


def test_memory_runtime_stays_disabled_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in _MEMORY_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)

    def unexpected_database_connection(database_url: str) -> None:
        pytest.fail("disabled knowledge memory must not create database engines")

    monkeypatch.setattr(
        main_module, "create_session_factory", unexpected_database_connection
    )
    application = create_app(Settings(environment="test"))

    with TestClient(application):
        assert application.state.knowledge_runtime is None


def test_memory_runtime_verifies_roles_and_builds_a_store_per_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_memory(monkeypatch)
    engines = _install_fake_database(monkeypatch)
    application = create_app(Settings(environment="test"))

    with TestClient(application):
        runtime = application.state.knowledge_runtime
        assert runtime is not None
        assert runtime.embedding_space.provider == "openai-compatible"
        assert runtime.embedding_space.dimensions == 3

        first_tenant = TenantContext(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            membership_id=UUID("00000000-0000-0000-0000-000000000011"),
            tenant_slug="acme",
            role="analyst",
            subject="oidc|analyst-a",
        )
        second_tenant = TenantContext(
            tenant_id=UUID("00000000-0000-0000-0000-000000000002"),
            membership_id=UUID("00000000-0000-0000-0000-000000000022"),
            tenant_slug="contoso",
            role="analyst",
            subject="oidc|analyst-b",
        )
        first_store = runtime.for_tenant(first_tenant)
        second_store = runtime.for_tenant(second_tenant)

        assert first_store is not second_store
        assert first_store._tenant_id == first_tenant.tenant_id
        assert first_store._subject == first_tenant.subject
        assert second_store._tenant_id == second_tenant.tenant_id
        assert second_store._subject == second_tenant.subject

    assert len(engines) == 2
    assert all(engine.disposed for engine in engines)
    assert application.state.knowledge_runtime is None


def test_wrong_database_role_fails_startup_and_disposes_both_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_memory(monkeypatch)
    engines = _install_fake_database(
        monkeypatch,
        roles={"aegis_ingestor": "aegis_runtime"},
    )
    application = create_app(Settings(environment="test"))

    with (
        pytest.raises(RuntimeError, match="role verification failed for aegis_ingestor"),
        TestClient(application),
    ):
        pass

    assert len(engines) == 2
    assert all(engine.disposed for engine in engines)
    assert application.state.knowledge_runtime is None


def test_database_connection_failure_is_sanitized_and_disposes_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_memory(monkeypatch)
    engines = _install_fake_database(
        monkeypatch,
        errors={"aegis_runtime": SQLAlchemyError("connection password leaked")},
    )
    application = create_app(Settings(environment="test"))

    with (
        pytest.raises(RuntimeError, match="role verification failed") as exc_info,
        TestClient(application),
    ):
        pass

    assert "connection password leaked" not in str(exc_info.value)
    assert len(engines) == 2
    assert all(engine.disposed for engine in engines)


def test_partial_memory_configuration_fails_before_opening_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in _MEMORY_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(
        "AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL",
        _MEMORY_ENVIRONMENT["AEGIS_KNOWLEDGE_RUNTIME_DATABASE_URL"],
    )

    def unexpected_database_connection(database_url: str) -> None:
        pytest.fail("partial knowledge configuration must not create database engines")

    monkeypatch.setattr(
        main_module, "create_session_factory", unexpected_database_connection
    )
    application = create_app(Settings(environment="test"))

    with (
        pytest.raises(ValidationError, match="knowledge memory configuration is incomplete"),
        TestClient(application),
    ):
        pass
