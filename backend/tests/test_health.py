"""Contract tests for the initial AEGIS API health surface."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_liveness_reports_only_process_state() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_discloses_unconfigured_external_dependencies() -> None:
    settings = Settings(app_name="AEGIS test API", environment="test")
    client = TestClient(create_app(settings))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "AEGIS test API",
        "environment": "test",
        "checks": {
            "application": "ready",
            "external_dependencies": "not_configured",
        },
    }


def test_production_disables_interactive_api_documentation() -> None:
    client = TestClient(create_app(Settings(environment="production")))

    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404

    assert client.get("/health/live").status_code == 200


def test_settings_reject_blank_app_name() -> None:
    with pytest.raises(ValidationError):
        Settings(app_name="   ")


def test_settings_reject_unknown_environment_and_log_level() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production-like")

    with pytest.raises(ValidationError):
        Settings(log_level="TRACE")


def test_settings_load_only_documented_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_APP_NAME", "  AEGIS Staging  ")
    monkeypatch.setenv("AEGIS_ENVIRONMENT", "staging")
    monkeypatch.setenv("AEGIS_LOG_LEVEL", "WARNING")

    settings = Settings.from_environment()

    assert settings.app_name == "AEGIS Staging"
    assert settings.environment == "staging"
    assert settings.log_level == "WARNING"
