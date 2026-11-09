"""Tests for trusted bearer verification and request-scoped identity."""

from fastapi import Depends
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security.authentication import (
    CredentialVerificationUnavailable,
    get_current_principal,
)
from app.security.identity import Principal, PrincipalType


class StubVerifier:
    def __init__(
        self,
        principal: Principal | None = None,
        error: Exception | None = None,
    ) -> None:
        self.principal = principal
        self.error = error
        self.seen_token: str | None = None

    async def verify(self, token: str, /) -> Principal | None:
        self.seen_token = token
        if self.error is not None:
            raise self.error
        return self.principal


def make_client(verifier: object | None = None) -> TestClient:
    application = create_app(
        Settings(environment="test"),
        credential_verifier=verifier,  # type: ignore[arg-type]
    )

    # This probe is registered only in the test application, never in AEGIS.
    @application.get("/_test/principal")
    async def principal_probe(
        principal: Principal = Depends(get_current_principal),
    ) -> dict[str, str]:
        return {"subject": principal.subject}

    return TestClient(application)


def test_missing_credentials_are_rejected_before_verifier() -> None:
    verifier = StubVerifier(
        Principal(subject="trusted-user", principal_type=PrincipalType.USER)
    )
    response = make_client(verifier).get("/_test/principal")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert verifier.seen_token is None


def test_non_bearer_authorization_scheme_is_rejected() -> None:
    response = make_client(StubVerifier()).get(
        "/_test/principal",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401


def test_empty_and_malformed_bearer_credentials_are_rejected() -> None:
    client = make_client(StubVerifier())
    for header in ("Bearer", "Bearer token with spaces", "Bearer \\u0001bad"):
        response = client.get("/_test/principal", headers={"Authorization": header})
        assert response.status_code == 401


def test_oversized_bearer_credential_is_rejected() -> None:
    response = make_client(StubVerifier()).get(
        "/_test/principal",
        headers={"Authorization": f"Bearer {'a' * 8193}"},
    )
    assert response.status_code == 401


def test_missing_verifier_fails_closed_without_creating_identity() -> None:
    response = make_client().get(
        "/_test/principal",
        headers={"Authorization": "Bearer syntactically-valid"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authentication_not_configured"


def test_unverified_credential_does_not_create_principal() -> None:
    verifier = StubVerifier(principal=None)
    response = make_client(verifier).get(
        "/_test/principal",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_or_missing_credentials"
    assert verifier.seen_token == "invalid-token"


def test_only_verified_principal_from_verifier_is_injected() -> None:
    principal = Principal(
        subject="trusted-service",
        principal_type=PrincipalType.SERVICE,
    )
    verifier = StubVerifier(principal=principal)
    response = make_client(verifier).get(
        "/_test/principal",
        headers={"Authorization": "Bearer verified-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"subject": "trusted-service"}
    assert verifier.seen_token == "verified-token"


def test_verifier_outage_fails_closed_without_leaking_provider_error() -> None:
    verifier = StubVerifier(
        error=CredentialVerificationUnavailable("provider detail")
    )
    response = make_client(verifier).get(
        "/_test/principal",
        headers={"Authorization": "Bearer opaque-token"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authentication_unavailable"
    assert "provider detail" not in response.text


def test_unexpected_verifier_failure_fails_closed() -> None:
    verifier = StubVerifier(error=RuntimeError("sensitive provider response"))
    response = make_client(verifier).get(
        "/_test/principal",
        headers={"Authorization": "Bearer opaque-token"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authentication_unavailable"
    assert "sensitive provider response" not in response.text


def test_verifier_cannot_return_unvalidated_identity_data() -> None:
    class UntrustedVerifier:
        async def verify(self, token: str, /) -> object:
            return {"subject": "attacker", "scopes": ["tool:execute"]}

    response = make_client(UntrustedVerifier()).get(
        "/_test/principal",
        headers={"Authorization": "Bearer opaque-token"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authentication_unavailable"


def test_caller_asserted_identity_headers_are_ignored() -> None:
    response = make_client().get(
        "/_test/principal",
        headers={
            "X-AEGIS-Subject": "attacker",
            "X-AEGIS-Scopes": "tool:execute",
        },
    )
    assert response.status_code == 401
