"""Configuration tests for KMS-backed webhook destination API."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_webhook_kms_key_is_loaded_from_environment_without_static_credentials() -> None:
    with patch.dict("os.environ", {
        "AEGIS_WEBHOOK_KMS_KEY_ID": "arn:aws:kms:us-east-1:123456789012:key/example",
        "AEGIS_WEBHOOK_KMS_REGION": "us-east-1",
    }, clear=True):
        settings = Settings.from_environment()
    assert settings.webhook_kms_key_id.endswith(":key/example")
    assert settings.webhook_kms_region == "us-east-1"
    assert "AWS_ACCESS_KEY_ID" not in repr(settings)


def test_kms_region_requires_key_reference() -> None:
    with pytest.raises(ValidationError):
        Settings(webhook_kms_region="us-east-1")


def test_blank_kms_key_reference_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(webhook_kms_key_id="   ")
