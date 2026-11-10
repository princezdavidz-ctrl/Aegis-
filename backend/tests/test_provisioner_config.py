"""Configuration tests for the separate tenant-provisioner database credential."""

from unittest.mock import patch

from app.config import Settings


def test_provisioner_database_url_is_loaded_as_a_secret() -> None:
    secret = "postgresql+asyncpg://aegis_provisioner:ci-placeholder@localhost/aegis"
    with patch.dict("os.environ", {"AEGIS_PROVISIONER_DATABASE_URL": secret}, clear=True):
        settings = Settings.from_environment()
    assert settings.provisioner_database_url is not None
    assert settings.provisioner_database_url.get_secret_value() == secret
    assert secret not in repr(settings)
