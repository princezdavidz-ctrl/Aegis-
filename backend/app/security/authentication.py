"""Provider-independent bearer verification and request identity injection.

A concrete trusted adapter must validate credentials and construct Principal
objects only after verification. This module deliberately ships without a
provider, key, token, or implicit development identity.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.identity import Principal

_BEARER_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9\\-._~+/]+=*$")
_MAX_BEARER_TOKEN_LENGTH = 8192
_bearer_scheme = HTTPBearer(auto_error=False)


@runtime_checkable
class CredentialVerifier(Protocol):
    """Trusted adapter for verifying opaque bearer credentials.

    Implementations must verify all provider-specific integrity and claims
    (including issuer, audience, expiry, and revocation where applicable) before
    returning an immutable Principal. They must never derive identity from
    unverified token claims.
    """

    async def verify(self, token: str, /) -> Principal | None:
        """Return a verified principal, or None for an invalid credential."""
        ...


class CredentialVerificationUnavailable(Exception):
    """Raised when a trusted credential provider cannot complete verification."""


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_or_missing_credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authentication_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="authentication_unavailable",
    )


async def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Principal:
    """Resolve a request principal only through the configured trusted verifier.

    Missing or malformed credentials are rejected with 401. If no verifier is
    configured, or verification infrastructure fails, the request fails closed
    with 503. No request header, query parameter, or body field can assert a
    principal directly.
    """

    if credentials is None:
        raise _unauthorized()

    token = credentials.credentials
    if (
        not token
        or len(token) > _MAX_BEARER_TOKEN_LENGTH
        or _BEARER_TOKEN_PATTERN.fullmatch(token) is None
    ):
        raise _unauthorized()

    verifier: CredentialVerifier | None = getattr(
        request.app.state, "credential_verifier", None
    )
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="authentication_not_configured",
        )

    try:
        principal = await verifier.verify(token)
    except Exception:
        # Do not leak provider errors or accidentally turn outages into access.
        raise _authentication_unavailable() from None

    if principal is None:
        raise _unauthorized()
    if not isinstance(principal, Principal):
        raise _authentication_unavailable()

    return principal
