"""Tests for outbound endpoint webhook security primitives."""
import pytest

from app.endpoint.webhooks import (
    WebhookConfigurationError,
    sign_webhook_payload,
    resolve_webhook_addresses,
    validate_webhook_url,
    verify_webhook_signature,
    webhook_retry_delay_seconds,
)


@pytest.mark.parametrize("url", [
    "http://example.com/hook",
    "https://localhost/hook",
    "https://sensor.local/hook",
    "https://127.0.0.1/hook",
    "https://[::1]/hook",
    "https://user:pass@example.com/hook",
    "https://example.com:8443/hook",
    "https://example.com/hook?token=secret",
    "https://example.com/hook#fragment",
    "https://singlelabel/hook",
])
def test_rejects_unsafe_webhook_destinations(url):
    with pytest.raises(WebhookConfigurationError):
        validate_webhook_url(url)


def test_accepts_https_dns_destination_without_rewriting_it():
    url = "https://alerts.example.org/aegis/endpoint"
    assert validate_webhook_url(url) == url


def test_hmac_signature_verifies_exact_body_and_timestamp():
    secret = b"s" * 32
    body = b'{"event":"endpoint.health","status":"offline"}'
    signature = sign_webhook_payload(secret, 1_800_000_000, body)
    assert signature.startswith("v1=")
    assert verify_webhook_signature(secret, 1_800_000_000, body, signature,
                                    now=1_800_000_100)
    assert not verify_webhook_signature(secret, 1_800_000_000, body + b" ",
                                        signature, now=1_800_000_100)
    assert not verify_webhook_signature(secret, 1_800_000_000, body,
                                        signature, now=1_800_000_500)


def test_signing_rejects_short_secrets_and_oversized_payloads():
    with pytest.raises(WebhookConfigurationError):
        sign_webhook_payload(b"short", 1_800_000_000, b"{}")
    with pytest.raises(WebhookConfigurationError):
        sign_webhook_payload(b"s" * 32, 1_800_000_000, b"x" * 1_048_577)


def test_retry_backoff_is_exponential_and_bounded():
    assert [webhook_retry_delay_seconds(i) for i in range(1, 5)] == [5, 10, 20, 40]
    assert webhook_retry_delay_seconds(20) == 900
    with pytest.raises(ValueError):
        webhook_retry_delay_seconds(0)



def _dns_record(address):
    import socket
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


def test_dns_resolution_returns_only_public_pinnable_addresses():
    records = [_dns_record("8.8.8.8"), _dns_record("1.1.1.1")]
    assert resolve_webhook_addresses(
        "https://alerts.example.org/hook",
        resolver=lambda *_args, **_kwargs: records,
    ) == ("1.1.1.1", "8.8.8.8")


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.8", "169.254.169.254", "::1", "fc00::1",
    "fe80::1", "224.0.0.1", "192.0.2.10",
])
def test_dns_resolution_rejects_non_global_and_mixed_answers(address):
    records = [_dns_record("8.8.8.8"), _dns_record(address)]
    with pytest.raises(WebhookConfigurationError):
        resolve_webhook_addresses(
            "https://alerts.example.org/hook",
            resolver=lambda *_args, **_kwargs: records,
        )


def test_dns_resolution_rejects_empty_and_failed_answers():
    with pytest.raises(WebhookConfigurationError):
        resolve_webhook_addresses(
            "https://alerts.example.org/hook",
            resolver=lambda *_args, **_kwargs: [],
        )
    def fail_lookup(*_args, **_kwargs):
        raise OSError("DNS unavailable")
    with pytest.raises(WebhookConfigurationError):
        resolve_webhook_addresses("https://alerts.example.org/hook", resolver=fail_lookup)
