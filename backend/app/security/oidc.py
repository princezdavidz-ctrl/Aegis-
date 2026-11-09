"""OIDC JWT credential verifier with issuer, audience and JWKS validation."""

from __future__ import annotations

import asyncio
from typing import Any

import jwt
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from app.security.authentication import CredentialVerificationUnavailable
from app.security.identity import Permission, Principal, PrincipalType


class OidcJwtCredentialVerifier:
    """Verify RS256 bearer JWTs against a trusted OIDC issuer and JWKS endpoint.

    Only explicitly recognized AEGIS scopes are mapped into the Principal.
    Unknown provider scopes are ignored rather than granting new capabilities.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        clock_skew_seconds: int = 30,
    ) -> None:
        if not issuer or not audience or not jwks_url:
            raise ValueError("OIDC issuer, audience and JWKS URL are required")
        if not 0 <= clock_skew_seconds <= 300:
            raise ValueError("OIDC clock skew must be between 0 and 300 seconds")
        self._issuer = issuer
        self._audience = audience
        self._clock_skew_seconds = clock_skew_seconds
        self._jwks_client = jwt.PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
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
