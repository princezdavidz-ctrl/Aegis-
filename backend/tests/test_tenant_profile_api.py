"""Tenant profile API authorization and input validation tests."""
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.security.identity import Principal, PrincipalType
from app.security.tenant import TenantContext, get_tenant_context

class StaticVerifier:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal
    async def verify(self, token: str, /) -> Principal | None:
        return self.principal if token == "valid-test-token" else None

def client_for(principal: Principal, role: str) -> TestClient:
    app = create_app(Settings(environment="test"), credential_verifier=StaticVerifier(principal))
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        membership_id="00000000-0000-0000-0000-000000000002",
        tenant_slug="acme", role=role, subject=principal.subject,
    )
    return TestClient(app)

def test_profile_update_denies_non_admin() -> None:
    principal = Principal(subject="oidc|analyst", principal_type=PrincipalType.USER)
    with client_for(principal, "analyst") as client:
        response = client.patch("/api/v1/tenants/profile",
            json={"industry":"Healthcare"},
            headers={"Authorization":"Bearer valid-test-token"})
    assert response.status_code == 403

def test_profile_update_rejects_invalid_retention() -> None:
    principal = Principal(subject="oidc|admin", principal_type=PrincipalType.USER)
    with client_for(principal, "tenant_admin") as client:
        response = client.patch("/api/v1/tenants/profile",
            json={"data_retention_days":10},
            headers={"Authorization":"Bearer valid-test-token"})
    assert response.status_code == 422

def test_profile_update_rejects_unknown_policy_profile() -> None:
    principal = Principal(subject="oidc|admin", principal_type=PrincipalType.USER)
    with client_for(principal, "tenant_admin") as client:
        response = client.patch("/api/v1/tenants/profile",
            json={"policy_profile":"unrestricted"},
            headers={"Authorization":"Bearer valid-test-token"})
    assert response.status_code == 422

def test_profile_update_fails_closed_without_provisioner_connection() -> None:
    principal = Principal(subject="oidc|admin", principal_type=PrincipalType.USER)
    with client_for(principal, "tenant_admin") as client:
        response = client.patch("/api/v1/tenants/profile",
            json={"industry":"Healthcare"},
            headers={"Authorization":"Bearer valid-test-token"})
    assert response.status_code == 503

def test_profile_update_rejects_empty_patch() -> None:
    principal = Principal(subject="oidc|admin", principal_type=PrincipalType.USER)
    with client_for(principal, "tenant_admin") as client:
        response = client.patch("/api/v1/tenants/profile",
            json={},
            headers={"Authorization":"Bearer valid-test-token"})
    assert response.status_code == 422
