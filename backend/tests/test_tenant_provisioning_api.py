"""Authorization boundary tests for platform tenant provisioning."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security.identity import Permission, Principal, PrincipalType


class StaticVerifier:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def verify(self, token: str, /) -> Principal | None:
        if token != "valid-test-token":
            return None
        return self.principal


def client_for(principal: Principal) -> TestClient:
    application = create_app(
        Settings(environment="test"),
        credential_verifier=StaticVerifier(principal),
    )
    return TestClient(application)


def payload() -> dict[str, str]:
    return {
        "slug": "acme-security",
        "display_name": "Acme Security",
        "initial_admin_subject": "oidc|customer-admin",
    }


def test_tenant_provisioning_requires_exact_platform_scope() -> None:
    principal = Principal(
        subject="oidc|analyst",
        principal_type=PrincipalType.USER,
        scopes=frozenset({Permission.INVESTIGATION_READ}),
    )
    with client_for(principal) as client:
        response = client.post(
            "/api/v1/tenants",
            json=payload(),
            headers={"Authorization": "Bearer valid-test-token"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "tenant_provision_not_permitted"


def test_tenant_provisioning_fails_closed_without_isolated_database_role() -> None:
    principal = Principal(
        subject="oidc|platform-admin",
        principal_type=PrincipalType.USER,
        scopes=frozenset({Permission.TENANT_PROVISION}),
    )
    with client_for(principal) as client:
        response = client.post(
            "/api/v1/tenants",
            json=payload(),
            headers={"Authorization": "Bearer valid-test-token"},
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "tenant_provisioner_unavailable"


def test_tenant_provisioning_rejects_client_supplied_tenant_id() -> None:
    principal = Principal(
        subject="oidc|platform-admin",
        principal_type=PrincipalType.USER,
        scopes=frozenset({Permission.TENANT_PROVISION}),
    )
    body = payload()
    body["tenant_id"] = "00000000-0000-0000-0000-000000000001"
    with client_for(principal) as client:
        response = client.post(
            "/api/v1/tenants",
            json=body,
            headers={"Authorization": "Bearer valid-test-token"},
        )
    assert response.status_code == 422


def test_tenant_provisioning_validates_slug_before_database_access() -> None:
    principal = Principal(
        subject="oidc|platform-admin",
        principal_type=PrincipalType.USER,
        scopes=frozenset({Permission.TENANT_PROVISION}),
    )
    body = payload()
    body["slug"] = "Acme Security"
    with client_for(principal) as client:
        response = client.post(
            "/api/v1/tenants",
            json=body,
            headers={"Authorization": "Bearer valid-test-token"},
        )
    assert response.status_code == 422
