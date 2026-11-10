"""OIDC JWT credential verifier with issuer, audience and JWKS validation."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from app.security.authentication import CredentialVerificationUnavailable
from app.security.identity import Permission, Principal, PrincipalType

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_JWKS_UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS = 30


def _validate_trusted_endpoint(
    value: str,
    name: str,
    *,
    allow_loopback_http: bool,
) -> None:
    """Require TLS for OIDC endpoints except explicit local development tests."""

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        # Accessing .port validates malformed port values as well.
        _ = parsed.port
    except ValueError:
        raise ValueError(f"{name} must be a valid absolute URL") from None

    secure = parsed.scheme == "https"
    local_test_endpoint = (
        allow_loopback_http
        and parsed.scheme == "http"
        and hostname in _LOOPBACK_HOSTS
    )
    if (
        not hostname
        or not (secure or local_test_endpoint)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} must use HTTPS (HTTP is allowed only for loopback tests)")


class OidcJwtCredentialVerifier:
    """Verify RS256 bearer JWTs against a trusted OIDC issuer and JWKS endpoint.

    Only explicitly recognized AEGIS scopes are mapped into the Principal.
    Unknown provider scopes are ignored rather than granting new capabilities.
    JWKS documents are cached for a bounded interval; an unknown key ID causes
    PyJWKClient to refresh the document before rejecting the credential.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        clock_skew_seconds: int = 30,
        jwks_cache_seconds: int = 300,
        allow_loopback_http: bool = False,
    ) -> None:
        if not issuer or not audience.strip() or not jwks_url:
            raise ValueError("OIDC issuer, audience and JWKS URL are required")
        _validate_trusted_endpoint(
            issuer, "OIDC issuer", allow_loopback_http=allow_loopback_http
        )
        _validate_trusted_endpoint(
            jwks_url, "OIDC JWKS URL", allow_loopback_http=allow_loopback_http
        )
        if not 0 <= clock_skew_seconds <= 300:
            raise ValueError("OIDC clock skew must be between 0 and 300 seconds")
        if not 30 <= jwks_cache_seconds <= 600:
            raise ValueError("OIDC JWKS cache must be between 30 and 600 seconds")
        self._issuer = issuer
        self._audience = audience
        self._clock_skew_seconds = clock_skew_seconds
        self._jwks_cache_seconds = jwks_cache_seconds
        self._jwks_client = jwt.PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=jwks_cache_seconds,
            timeout=5,
            cooldown_duration=_JWKS_UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS,
        )

    async def verify(self, token: str, /) -> Principal | None:
        """Return a principal only after signature and standard claims validate."""

        try:
            signing_key = await asyncio.to_thread(
                self._jwks_client.get_signing_key_from_jwt, token
            )
        except PyJWKClientConnectionError:
            raise CredentialVerificationUnavailable from None
        except PyJWKClientError:
            return None

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._clock_skew_seconds,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.InvalidTokenError:
            return None

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            return None

        raw_scope = claims.get("scope", "")
        recognized = {permission.value: permission for permission in Permission}
        if isinstance(raw_scope, str):
            scopes = frozenset(
                recognized[scope]
                for scope in raw_scope.split()
                if scope in recognized
            )
        else:
            scopes = frozenset()

        try:
            return Principal(
                subject=subject,
                principal_type=PrincipalType.USER,
                scopes=scopes,
            )
        except ValueError:
            return None
