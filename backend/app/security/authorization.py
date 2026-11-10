"""Pure deny-by-default authorization decisions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from app.security.identity import Permission, Principal


class AuthorizationReason(StrEnum):
    GRANTED = "granted"
    MISSING_PRINCIPAL = "missing_principal"
    MISSING_SCOPE = "missing_scope"


class AuthorizationDecision(BaseModel):
    """A complete, immutable explanation of one exact-scope check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    required_scope: Permission
    reason: AuthorizationReason
    subject: str | None = None

    @model_validator(mode="after")
    def validate_decision_consistency(self) -> AuthorizationDecision:
        if self.allowed != (self.reason == AuthorizationReason.GRANTED):
            raise ValueError("allowed must be true exactly when the reason is granted")
        if (self.reason == AuthorizationReason.MISSING_PRINCIPAL) != (self.subject is None):
            raise ValueError("only a missing-principal decision may omit the subject")
        return self


def authorize(principal: Principal | None, required_scope: Permission) -> AuthorizationDecision:
    """Grant only an exact declared scope; missing identity or scope is denied."""

    if principal is None:
        return AuthorizationDecision(
            allowed=False,
            required_scope=required_scope,
            reason=AuthorizationReason.MISSING_PRINCIPAL,
        )

    if required_scope not in principal.scopes:
        return AuthorizationDecision(
            allowed=False,
            required_scope=required_scope,
            reason=AuthorizationReason.MISSING_SCOPE,
            subject=principal.subject,
        )

    return AuthorizationDecision(
        allowed=True,
        required_scope=required_scope,
        reason=AuthorizationReason.GRANTED,
        subject=principal.subject,
    )
