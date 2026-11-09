"""OIDC JWT verifier tests with an isolated signing key."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import PyJWKClientConnectionError

from app.security.authentication import CredentialVerificationUnavailable
from app.security.identity import Permission
from app.security.oidc import OidcJwtCredentialVerifier

ISSUER = "https://identity.example.test/"
AUDIENCE = "aegis-api"


@pytest.fixture
def key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def make_verifier(public_key):
    verifier = OidcJwtCredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="https://identity.example.test/.well-known/jwks.json",
    )
    verifier._jwks_client.get_signing_key_from_jwt = lambda _token: SimpleNamespace(
        key=public_key
    )
    return verifier


def make_token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "oidc|analyst-123",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "scope": "telemetry:read investigation:read unknown:admin",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.asyncio
async def test_valid_oidc_token_maps_only_known_aegis_scopes(key_pair) -> None:
    private_key, public_key = key_pair
    verifier = make_verifier(public_key)
    principal = await verifier.verify(make_token(private_key))
    assert principal is not None
    assert principal.subject == "oidc|analyst-123"
    assert principal.scopes == frozenset({
        Permission.TELEMETRY_READ,
        Permission.INVESTIGATION_READ,
    })


@pytest.mark.asyncio
async def test_wrong_issuer_is_rejected(key_pair) -> None:
    private_key, public_key = key_pair
    verifier = make_verifier(public_key)
    assert await verifier.verify(make_token(private_key, iss="https://attacker.test/")) is None


@pytest.mark.asyncio
async def test_wrong_audience_is_rejected(key_pair) -> None:
    private_key, public_key = key_pair
    verifier = make_verifier(public_key)
    assert await verifier.verify(make_token(private_key, aud="other-api")) is None


@pytest.mark.asyncio
async def test_expired_token_is_rejected(key_pair) -> None:
    private_key, public_key = key_pair
    verifier = make_verifier(public_key)
    old = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    assert await verifier.verify(make_token(private_key, exp=old, iat=old - 60)) is None


@pytest.mark.asyncio
async def test_missing_required_claim_is_rejected(key_pair) -> None:
    private_key, public_key = key_pair
    verifier = make_verifier(public_key)
    token = make_token(private_key)
    claims = jwt.decode(token, public_key, algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER)
    claims.pop("sub")
    now = datetime.now(timezone.utc)
    claims["iat"] = int(now.timestamp())
    claims["exp"] = int((now + timedelta(minutes=5)).timestamp())
    token_without_subject = jwt.encode(claims, private_key, algorithm="RS256")
    assert await verifier.verify(token_without_subject) is None


@pytest.mark.asyncio
async def test_jwks_network_failure_fails_closed_as_unavailable(key_pair) -> None:
    _, public_key = key_pair
    verifier = make_verifier(public_key)

    def unavailable(_token):
        raise PyJWKClientConnectionError("provider offline")

    verifier._jwks_client.get_signing_key_from_jwt = unavailable
    with pytest.raises(CredentialVerificationUnavailable):
        await verifier.verify("opaque-token")
