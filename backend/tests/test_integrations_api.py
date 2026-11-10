"""Integration registry API authorization and scope validation tests."""
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.security.identity import Principal,PrincipalType
from app.security.tenant import TenantContext,get_tenant_context

class StaticVerifier:
 def __init__(self,p: Principal):self.p=p
 async def verify(self,token: str,/) -> Principal | None:return self.p if token=="valid-test-token" else None

def client_for(p: Principal,role: str) -> TestClient:
 app=create_app(Settings(environment="test"),credential_verifier=StaticVerifier(p))
 app.dependency_overrides[get_tenant_context]=lambda:TenantContext(
  tenant_id="00000000-0000-0000-0000-000000000001",
  membership_id="00000000-0000-0000-0000-000000000002",
  tenant_slug="acme",role=role,subject=p.subject)
 return TestClient(app)

def test_viewer_cannot_request_integration() -> None:
 p=Principal(subject="oidc|viewer",principal_type=PrincipalType.USER)
 with client_for(p,"viewer") as c:
  r=c.post("/api/v1/integrations",json={"provider":"github","display_name":"GitHub","requested_scopes":["repositories:read"]},headers={"Authorization":"Bearer valid-test-token"})
 assert r.status_code==403

def test_provider_scope_allowlist_rejects_write_scope() -> None:
 p=Principal(subject="oidc|manager",principal_type=PrincipalType.USER)
 with client_for(p,"security_manager") as c:
  r=c.post("/api/v1/integrations",json={"provider":"github","display_name":"GitHub","requested_scopes":["repositories:write"]},headers={"Authorization":"Bearer valid-test-token"})
 assert r.status_code==422

def test_unknown_provider_is_rejected() -> None:
 p=Principal(subject="oidc|manager",principal_type=PrincipalType.USER)
 with client_for(p,"security_manager") as c:
  r=c.post("/api/v1/integrations",json={"provider":"unknown","display_name":"X","requested_scopes":["alerts:read"]},headers={"Authorization":"Bearer valid-test-token"})
 assert r.status_code==422

def test_raw_credentials_are_rejected_by_schema() -> None:
 p=Principal(subject="oidc|manager",principal_type=PrincipalType.USER)
 with client_for(p,"security_manager") as c:
  r=c.post("/api/v1/integrations",json={"provider":"github","display_name":"GitHub","requested_scopes":["repositories:read"],"access_token":"never-store-this"},headers={"Authorization":"Bearer valid-test-token"})
 assert r.status_code==422

def test_security_manager_cannot_approve_integration() -> None:
 p=Principal(subject="oidc|manager",principal_type=PrincipalType.USER)
 with client_for(p,"security_manager") as c:
  r=c.post("/api/v1/integrations/00000000-0000-0000-0000-000000000001/approve",json={"approved_scopes":["repositories:read"]},headers={"Authorization":"Bearer valid-test-token"})
 assert r.status_code==403

def test_integration_request_fails_closed_without_provisioner() -> None:
 p=Principal(subject="oidc|manager",principal_type=PrincipalType.USER)
 with client_for(p,"security_manager") as c:
  r=c.post("/api/v1/integrations",json={"provider":"github","display_name":"GitHub","requested_scopes":["repositories:read"]},headers={"Authorization":"Bearer valid-test-token"})
 assert r.status_code==503
