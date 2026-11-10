"""OIDC JWT verifier tests with isolated signing keys and a local JWKS endpoint."""

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
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


def make_token(private_key, *, kid="test-key", **overrides):
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
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def jwk_for(public_key, kid):
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return jwk


@pytest.fixture
def local_jwks_endpoint():
    class Handler(BaseHTTPRequestHandler):
        payload = {"keys": []}
        requests = 0

        def do_GET(self):
            Handler.requests += 1
            body = json.dumps(self.payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def set_keys(*keys):
        Handler.payload = {"keys": list(keys)}

    def request_count():
        return Handler.requests

    try:
        yield (
            f"http://127.0.0.1:{server.server_port}/.well-known/jwks.json",
            set_keys,
            request_count,
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


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


@pytest.mark.asyncio
async def test_real_jwks_rotation_refreshes_new_kid_and_rejects_removed_key(
    local_jwks_endpoint,
) -> None:
    first_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    second_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks_url, set_keys, request_count = local_jwks_endpoint
    set_keys(jwk_for(first_private.public_key(), "key-1"))
    verifier = OidcJwtCredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=jwks_url,
        jwks_cache_seconds=60,
        allow_loopback_http=True,
    )

    first = await verifier.verify(make_token(first_private, kid="key-1"))
    assert first is not None

    # A new key ID is not accepted during the anti-abuse refresh cooldown.
    set_keys(jwk_for(second_private.public_key(), "key-2"))
    second_token = make_token(second_private, kid="key-2")
    assert await verifier.verify(second_token) is None
    assert request_count() == 1

    # Once the cooldown has elapsed, the unknown kid triggers one JWKS refresh.
    verifier._jwks_client._last_successful_fetch = (
        time.monotonic() - verifier._jwks_client.cooldown_duration - 1
    )
    second = await verifier.verify(second_token)
    assert second is not None
    assert request_count() == 2

    # The old key is no longer in the refreshed document and cannot validate.
    assert await verifier.verify(make_token(first_private, kid="key-1")) is None
    assert request_count() == 2


def test_oidc_endpoints_require_https_except_loopback() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OidcJwtCredentialVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url="http://identity.example.test/jwks.json",
        )

    with pytest.raises(ValueError, match="HTTPS"):
        OidcJwtCredentialVerifier(
            issuer="http://identity.example.test/",
            audience=AUDIENCE,
            jwks_url="https://identity.example.test/jwks.json",
        )

    with pytest.raises(ValueError, match="HTTPS"):
        OidcJwtCredentialVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url="http://127.0.0.1:9000/jwks.json",
        )


def test_jwks_cache_lifetime_is_bounded() -> None:
    with pytest.raises(ValueError, match="30 and 600"):
        OidcJwtCredentialVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url="https://identity.example.test/jwks.json",
            jwks_cache_seconds=601,
        )
