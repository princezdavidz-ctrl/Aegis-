"""Tests for KMS-backed webhook secret envelope encryption."""
import os

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.endpoint.webhook_secrets import (
    KMSWebhookSecretProvider,
    WebhookSecretEncryptionError,
)


class FakeKMS:
    def __init__(self):
        self.master = os.urandom(32)

    def generate_data_key(self, **kwargs):
        key, nonce = os.urandom(32), os.urandom(12)
        aad = repr(sorted(kwargs["EncryptionContext"].items())).encode()
        return {"Plaintext": key, "CiphertextBlob": nonce + AESGCM(self.master).encrypt(nonce, key, aad)}

    def decrypt(self, **kwargs):
        aad = repr(sorted(kwargs["EncryptionContext"].items())).encode()
        blob = kwargs["CiphertextBlob"]
        return {"Plaintext": AESGCM(self.master).decrypt(blob[:12], blob[12:], aad)}


def test_round_trip_binds_tenant_destination_and_secret_version():
    provider = KMSWebhookSecretProvider(FakeKMS(), "arn:aws:kms:us-east-1:123456789012:key/test")
    secret = os.urandom(48)
    envelope = provider.encrypt(secret, tenant_id="tenant-a", destination_id="dest-1")
    assert secret not in envelope
    assert provider.decrypt(envelope, tenant_id="tenant-a", destination_id="dest-1") == secret


@pytest.mark.parametrize("context", [
    {"tenant_id": "tenant-b", "destination_id": "dest-1"},
    {"tenant_id": "tenant-a", "destination_id": "dest-2"},
    {"tenant_id": "tenant-a", "destination_id": "dest-1", "secret_version": 2},
])
def test_wrong_context_cannot_decrypt(context):
    provider = KMSWebhookSecretProvider(FakeKMS(), "kms-key")
    envelope = provider.encrypt(b"s" * 32, tenant_id="tenant-a", destination_id="dest-1")
    with pytest.raises(WebhookSecretEncryptionError):
        provider.decrypt(envelope, **context)


def test_modified_envelope_is_rejected():
    provider = KMSWebhookSecretProvider(FakeKMS(), "kms-key")
    envelope = bytearray(provider.encrypt(b"s" * 32, tenant_id="tenant-a", destination_id="dest-1"))
    envelope[-1] ^= 1
    with pytest.raises(WebhookSecretEncryptionError):
        provider.decrypt(bytes(envelope), tenant_id="tenant-a", destination_id="dest-1")


@pytest.mark.parametrize("secret", [b"short", b"x" * 4097, "not-bytes"])
def test_invalid_secrets_are_rejected(secret):
    provider = KMSWebhookSecretProvider(FakeKMS(), "kms-key")
    with pytest.raises(WebhookSecretEncryptionError):
        provider.encrypt(secret, tenant_id="tenant-a", destination_id="dest-1")


def test_key_reference_is_required():
    with pytest.raises(WebhookSecretEncryptionError):
        KMSWebhookSecretProvider(FakeKMS(), "")
