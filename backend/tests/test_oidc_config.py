"""Configuration tests for OIDC JWKS refresh policy."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_jwks_cache_lifetime_can_be_tuned_within_safe_bounds() -> None:
    with patch.dict(
        "os.environ",
        {
            "AEGIS_OIDC_ISSUER": "https://identity.example.test/",
            "AEGIS_OIDC_AUDIENCE": "aegis-api",
            "AEGIS_OIDC_JWKS_URL": "https://identity.example.test/jwks.json",
            "AEGIS_OIDC_JWKS_CACHE_SECONDS": "90",
        },
        clear=True,
    ):
        settings = Settings.from_environment()
    assert settings.oidc_jwks_cache_seconds == 90


def test_invalid_jwks_cache_lifetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(oidc_jwks_cache_seconds=601)
