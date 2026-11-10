"""Tenant membership API authorization and validation tests."""
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

def client_for(principal: Principal, tenant_role: str) -> TestClient:
    application = create_app(Settings(environment="test"), credential_verifier=StaticVerifier(principal))
    application.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        membership_id="00000000-0000-0000-0000-000000000002",
        tenant_slug="acme", role=tenant_role, subject=principal.subject,
    )
    return TestClient(application)

def test_membership_list_denies_non_admin() -> None:
    principal = Principal(subject="oidc|analyst", principal_type=PrincipalType.USER)
    with client_for(principal, "analyst") as client:
        response = client.get("/api/v1/tenants/members", headers={"Authorization": "Bearer valid-test-token"})
    assert response.status_code == 403

def test_membership_invitation_denies_non_admin() -> None:
    principal = Principal(subject="oidc|analyst", principal_type=PrincipalType.USER)
    with client_for(principal, "analyst") as client:
        response = client.post("/api/v1/tenants/members/invitations",
            json={"subject": "oidc|new-user", "role": "viewer"},
            headers={"Authorization": "Bearer valid-test-token"})
    assert response.status_code == 403

def test_membership_invitation_rejects_admin_role_assignment() -> None:
    principal = Principal(subject="oidc|admin", principal_type=PrincipalType.USER)
    with client_for(principal, "tenant_admin") as client:
        response = client.post("/api/v1/tenants/members/invitations",
            json={"subject": "oidc|new-user", "role": "tenant_admin"},
            headers={"Authorization": "Bearer valid-test-token"})
    assert response.status_code == 422

def test_membership_update_rejects_unknown_action() -> None:
    principal = Principal(subject="oidc|admin", principal_type=PrincipalType.USER)
    with client_for(principal, "tenant_admin") as client:
        response = client.patch("/api/v1/tenants/members/oidc%7Cmember",
            json={"action": "promote_to_superadmin"},
            headers={"Authorization": "Bearer valid-test-token"})
    assert response.status_code == 422

def test_invitation_acceptance_fails_closed_without_provisioner() -> None:
    principal = Principal(subject="oidc|new-user", principal_type=PrincipalType.USER)
    application = create_app(Settings(environment="test"), credential_verifier=StaticVerifier(principal))
    with TestClient(application) as client:
        response = client.post("/api/v1/tenants/invitations/accept",
            json={"tenant_slug": "acme"},
            headers={"Authorization": "Bearer valid-test-token"})
    assert response.status_code == 503
