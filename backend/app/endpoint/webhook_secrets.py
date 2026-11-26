"""KMS-backed envelope encryption for endpoint webhook signing secrets."""
from __future__ import annotations

import os
import struct
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAGIC = b"AEGW"
_VERSION = 1
_NONCE_BYTES = 12
_TAG_BYTES = 16
_DATA_KEY_BYTES = 32
_MAX_SECRET_BYTES = 4096
_MAX_WRAPPED_KEY_BYTES = 8192
_PURPOSE = "aegis:endpoint-webhook-signing-secret"


class KMSClient(Protocol):
    def generate_data_key(self, **kwargs) -> dict: ...
    def decrypt(self, **kwargs) -> dict: ...


class WebhookSecretEncryptionError(ValueError):
    """Raised when webhook secret encryption or decryption fails."""


def _context(tenant_id: str, destination_id: str, secret_version: int) -> dict[str, str]:
    for value in (tenant_id, destination_id):
        if not isinstance(value, str) or not value or len(value) > 128:
            raise WebhookSecretEncryptionError("invalid webhook encryption context")
    if not isinstance(secret_version, int) or isinstance(secret_version, bool) or secret_version < 1:
        raise WebhookSecretEncryptionError("invalid webhook secret version")
    return {"purpose": _PURPOSE, "tenant_id": tenant_id,
            "destination_id": destination_id, "secret_version": str(secret_version)}


def _aad(context: dict[str, str]) -> bytes:
    return b"|".join(context[k].encode() for k in
                     ("purpose", "tenant_id", "destination_id", "secret_version"))


class KMSWebhookSecretProvider:
    """AES-256-GCM envelope encryption with AWS KMS-wrapped data keys."""

    def __init__(self, kms_client: KMSClient, key_id: str) -> None:
        if not isinstance(key_id, str) or not key_id.strip() or len(key_id) > 512:
            raise WebhookSecretEncryptionError("a configured KMS key reference is required")
        self._kms = kms_client
        self.key_id = key_id.strip()

    def encrypt(self, secret: bytes, *, tenant_id: str, destination_id: str,
                secret_version: int = 1) -> bytes:
        if not isinstance(secret, bytes) or not 32 <= len(secret) <= _MAX_SECRET_BYTES:
            raise WebhookSecretEncryptionError("webhook secret must be 32 to 4096 bytes")
        context = _context(tenant_id, destination_id, secret_version)
        try:
            response = self._kms.generate_data_key(
                KeyId=self.key_id, KeySpec="AES_256", EncryptionContext=context)
            data_key = response["Plaintext"]
            wrapped_key = response["CiphertextBlob"]
            if not isinstance(data_key, bytes) or len(data_key) != _DATA_KEY_BYTES:
                raise WebhookSecretEncryptionError("KMS returned an invalid data key")
            if not isinstance(wrapped_key, bytes) or not 1 <= len(wrapped_key) <= _MAX_WRAPPED_KEY_BYTES:
                raise WebhookSecretEncryptionError("KMS returned an invalid wrapped key")
            nonce = os.urandom(_NONCE_BYTES)
            ciphertext = AESGCM(data_key).encrypt(nonce, secret, _aad(context))
            return (_MAGIC + bytes((_VERSION,)) + nonce
                    + struct.pack(">H", len(wrapped_key)) + wrapped_key + ciphertext)
        except WebhookSecretEncryptionError:
            raise
        except Exception as exc:
            raise WebhookSecretEncryptionError("webhook secret encryption failed") from exc

    def decrypt(self, envelope: bytes, *, tenant_id: str, destination_id: str,
                secret_version: int = 1) -> bytes:
        context = _context(tenant_id, destination_id, secret_version)
        minimum = 4 + 1 + _NONCE_BYTES + 2 + 1 + _TAG_BYTES
        if not isinstance(envelope, bytes) or not minimum <= len(envelope) <= 16384:
            raise WebhookSecretEncryptionError("invalid webhook secret envelope")
        if envelope[:4] != _MAGIC or envelope[4] != _VERSION:
            raise WebhookSecretEncryptionError("unsupported webhook secret envelope")
        nonce = envelope[5:17]
        key_len = struct.unpack(">H", envelope[17:19])[0]
        key_start, key_end = 19, 19 + key_len
        if not 1 <= key_len <= _MAX_WRAPPED_KEY_BYTES or key_end + _TAG_BYTES > len(envelope):
            raise WebhookSecretEncryptionError("invalid webhook secret envelope")
        try:
            response = self._kms.decrypt(
                CiphertextBlob=envelope[key_start:key_end], EncryptionContext=context)
            data_key = response["Plaintext"]
            if not isinstance(data_key, bytes) or len(data_key) != _DATA_KEY_BYTES:
                raise WebhookSecretEncryptionError("KMS returned an invalid data key")
            plaintext = AESGCM(data_key).decrypt(nonce, envelope[key_end:], _aad(context))
            if not 32 <= len(plaintext) <= _MAX_SECRET_BYTES:
                raise WebhookSecretEncryptionError("decrypted secret has invalid length")
            return plaintext
        except WebhookSecretEncryptionError:
            raise
        except Exception as exc:
            raise WebhookSecretEncryptionError("webhook secret decryption failed") from exc
