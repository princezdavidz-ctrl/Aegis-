"""Tests for the authenticated advisory AI API boundary."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security.identity import Permission, Principal, PrincipalType
from app.security.authentication import get_current_principal
from app.security.tenant import TenantContext, get_tenant_context


def test_ai_analysis_requires_authentication() -> None:
    client = TestClient(create_app(Settings()))
    response = client.post(
        "/api/v1/ai/analysis",
        headers={"X-AEGIS-Tenant": "acme", "Authorization": "Bearer test-token"},
        json={
            "kind": "alert_triage",
            "evidence": [{"evidence_id": "evt-1", "source_type": "alert", "content": "suspicious login"}],
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authentication_not_configured"


def test_ai_analysis_requires_server_resolved_tenant_membership() -> None:
    app = create_app(Settings())
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        subject="analyst-1", principal_type=PrincipalType.USER,
        scopes=frozenset({Permission.INVESTIGATION_CREATE}),
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/analysis",
        headers={"X-AEGIS-Tenant": "acme"},
        json={
            "kind": "alert_triage",
            "evidence": [{"evidence_id": "evt-1", "source_type": "alert", "content": "suspicious login"}],
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "tenant_membership_store_unavailable"


def _validated_request_client() -> TestClient:
    app = create_app(Settings())
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        subject="analyst-1", principal_type=PrincipalType.USER,
        scopes=frozenset({Permission.INVESTIGATION_CREATE}),
    )
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=__import__("uuid").uuid4(), membership_id=__import__("uuid").uuid4(),
        tenant_slug="acme", role="analyst", subject="analyst-1",
    )
    return TestClient(app)


def test_ai_analysis_rejects_unknown_fields_and_invalid_kind() -> None:
    client = _validated_request_client()
    response = client.post(
        "/api/v1/ai/analysis",
        json={
            "kind": "shell_execution",
            "evidence": [{"evidence_id": "evt-1", "source_type": "alert", "content": "x"}],
            "command": "rm -rf /",
        },
    )
    assert response.status_code == 422


def test_ai_analysis_input_bounds_are_enforced() -> None:
    client = _validated_request_client()
    response = client.post(
        "/api/v1/ai/analysis",
        json={
            "kind": "alert_triage",
            "evidence": [
                {"evidence_id": "evt-1", "source_type": "alert", "content": "x" * 12_001}
            ],
        },
    )
    assert response.status_code == 422
