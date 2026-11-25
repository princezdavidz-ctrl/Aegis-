"""Security primitives for outbound endpoint-health webhooks.

Network delivery, DNS pinning, persistence and retries are deliberately owned
by the worker layer. These helpers fail closed at the configuration boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from urllib.parse import urlsplit

_MAX_BODY_BYTES = 1_048_576
_SECRET_MIN_BYTES = 32
_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class WebhookConfigurationError(ValueError):
    """Raised when a webhook destination or signing input is unsafe."""


def validate_webhook_url(value: str) -> str:
    """Accept only public-looking HTTPS DNS URLs; reject obvious SSRF inputs.

    This is a configuration-time guard, not a substitute for delivery-time
    DNS resolution checks and IP pinning. The worker must reject any resolved
    non-global address and connect to the validated pinned address.
    """
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise WebhookConfigurationError("invalid webhook URL")
    if any(ord(char) < 0x21 or ord(char) == 0x7F for char in value):
        raise WebhookConfigurationError("invalid webhook URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise WebhookConfigurationError("invalid webhook URL") from exc

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise WebhookConfigurationError("webhook URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise WebhookConfigurationError("webhook URL must not contain credentials")
    if parsed.fragment or parsed.query:
        raise WebhookConfigurationError("webhook URL must not contain query or fragment")
    if port not in (None, 443):
        raise WebhookConfigurationError("webhook URL must use port 443")

    host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
        raise WebhookConfigurationError("webhook host is not publicly routable")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise WebhookConfigurationError("webhook host must be a DNS name")
    labels = host.split(".")
    if len(labels) < 2 or any(not _DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise WebhookConfigurationError("invalid webhook hostname")
    return value


def sign_webhook_payload(secret: bytes, timestamp: int, body: bytes) -> str:
    """Return a versioned HMAC-SHA256 signature for an exact request body."""
    if not isinstance(secret, bytes) or len(secret) < _SECRET_MIN_BYTES:
        raise WebhookConfigurationError("webhook secret must contain at least 32 bytes")
    if not isinstance(timestamp, int) or timestamp <= 0:
        raise WebhookConfigurationError("invalid webhook timestamp")
    if not isinstance(body, bytes) or len(body) > _MAX_BODY_BYTES:
        raise WebhookConfigurationError("invalid webhook body")
    message = str(timestamp).encode("ascii") + b"." + body
    digest = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return "v1=" + digest


def verify_webhook_signature(
    secret: bytes,
    timestamp: int,
    body: bytes,
    signature: str,
    *,
    now: int,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify signature in constant time and reject stale/future timestamps."""
    if tolerance_seconds < 1 or tolerance_seconds > 3600:
        return False
    if abs(now - timestamp) > tolerance_seconds:
        return False
    try:
        expected = sign_webhook_payload(secret, timestamp, body)
    except (WebhookConfigurationError, TypeError):
        return False
    return isinstance(signature, str) and hmac.compare_digest(expected, signature)


def webhook_retry_delay_seconds(attempt: int, *, base_seconds: int = 5, cap_seconds: int = 900) -> int:
    """Bounded exponential backoff; attempt is one-based."""
    if attempt < 1 or base_seconds < 1 or cap_seconds < base_seconds:
        raise ValueError("invalid retry policy")
    return min(cap_seconds, base_seconds * (2 ** min(attempt - 1, 20)))
