"""API tests for tenant-scoped webhook destinations and KMS secret handling."""

import base64
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security.identity import Principal, PrincipalType
from app.security.tenant import TenantContext, get_tenant_context


class StaticVerifier:
    async def verify(self, token: str, /) -> Principal | None:
        if token == "valid-test-token":
            return Principal(subject="oidc|security-admin", principal_type=PrincipalType.USER)
        return None


def make_client(role: str = "security_manager") -> TestClient:
    app = create_app(Settings(environment="test"), credential_verifier=StaticVerifier())
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        membership_id="00000000-0000-0000-0000-000000000002",
        tenant_slug="acme",
        role=role,
        subject="oidc|security-admin",
    )
    return TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid-test-token"}


def test_create_rejects_non_public_or_non_https_targets() -> None:
    with make_client() as client:
        response = client.post("/api/v1/webhook-destinations", headers=auth_headers(), json={
            "name": "SOC alerts",
            "target_url": "https://127.0.0.1/internal",
            "event_types": ["endpoint.health"],
        })
    assert response.status_code == 422


def test_create_rejects_duplicate_or_invalid_event_types() -> None:
    with make_client() as client:
        response = client.post("/api/v1/webhook-destinations", headers=auth_headers(), json={
            "name": "SOC alerts",
            "target_url": "https://alerts.example.org/aegis",
            "event_types": ["endpoint.health", "endpoint.health"],
        })
    assert response.status_code == 422


def test_destination_api_denies_non_manager() -> None:
    with make_client(role="analyst") as client:
        response = client.get("/api/v1/webhook-destinations", headers=auth_headers())
    assert response.status_code == 403


def test_destination_api_fails_closed_when_kms_is_not_configured() -> None:
    with make_client() as client:
        response = client.post("/api/v1/webhook-destinations", headers=auth_headers(), json={
            "name": "SOC alerts",
            "target_url": "https://alerts.example.org/aegis",
            "event_types": ["endpoint.health"],
        })
    assert response.status_code == 503
    assert response.json()["detail"] == "webhook_kms_not_configured"


def test_create_returns_random_signing_secret_once_and_stores_only_ciphertext(monkeypatch) -> None:
    import app.api.webhook_destinations as api

    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    destination_id = uuid4()
    captured: dict[str, object] = {}

    class FakeProvider:
        key_id = "arn:aws:kms:us-east-1:123456789012:key/test"

        def encrypt(self, secret: bytes, **context: str) -> bytes:
            captured["plaintext"] = secret
            captured["context"] = context
            return b"E" * 80

    async def fake_create(factory, **kwargs):
        captured["repository"] = kwargs
        return {
            "id": destination_id,
            "name": kwargs["name"],
            "target_url": kwargs["target_url"],
            "status": "active",
            "event_types": kwargs["event_types"],
            "secret_version": 1,
            "created_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(api, "create_webhook_destination", fake_create)
    with make_client() as client:
        client.app.state.webhook_secret_provider = FakeProvider()
        client.app.state.provisioner_session_factory = object()
        response = client.post("/api/v1/webhook-destinations", headers=auth_headers(), json={
            "name": "SOC alerts",
            "target_url": "https://alerts.example.org/aegis",
            "event_types": ["endpoint.health"],
        })

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(destination_id)
    assert len(base64.urlsafe_b64decode(body["signing_secret"] + "==")) == 32
    assert captured["plaintext"] not in captured["repository"]["secret_ciphertext"]
    assert captured["repository"]["destination_id"] == destination_id
    assert captured["context"]["tenant_id"] == str(tenant_id)
    assert captured["context"]["destination_id"] == str(destination_id)
    assert "secret_ciphertext" not in body
    assert "secret_key_ref" not in body


def test_list_response_contract_does_not_expose_secret_material() -> None:
    from app.api.webhook_destinations import WebhookDestinationView

    item = WebhookDestinationView(
        id=uuid4(),
        name="SOC alerts",
        target_url="https://alerts.example.org/aegis",
        status="active",
        event_types=["endpoint.health"],
        secret_version=1,
        created_at=datetime.now(timezone.utc),
    )
    serialized = item.model_dump()
    assert "secret_ciphertext" not in serialized
    assert "secret_key_ref" not in serialized
    assert "signing_secret" not in serialized
