"""Authenticated membership bootstrap tests with isolated SQLite storage."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.base import Base
from app.db.models import MembershipStatus, Tenant, TenantMembership
from app.main import create_app
from app.security.identity import Principal, PrincipalType


class StaticVerifier:
    """Test-only verifier that returns a fixed principal for one opaque token."""

    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def verify(self, token: str, /) -> Principal | None:
        return self.principal if token == "verified-test-token" else None


@pytest.mark.asyncio
async def test_bootstrap_returns_only_current_subject_active_memberships() -> None:
    subject = "oidc|current-user"
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        tenants = [
            Tenant(id=uuid4(), slug="northstar-security", display_name="Northstar Security"),
            Tenant(id=uuid4(), slug="pending-organization", display_name="Pending Organization"),
            Tenant(id=uuid4(), slug="suspended-organization", display_name="Suspended Organization"),
            Tenant(id=uuid4(), slug="revoked-organization", display_name="Revoked Organization"),
            Tenant(id=uuid4(), slug="other-user-organization", display_name="Other User Organization"),
        ]
        statuses = [
            (subject, "tenant_admin", MembershipStatus.ACTIVE.value),
            (subject, "viewer", MembershipStatus.PENDING.value),
            (subject, "analyst", MembershipStatus.SUSPENDED.value),
            (subject, "viewer", MembershipStatus.REVOKED.value),
            ("oidc|different-user", "tenant_admin", MembershipStatus.ACTIVE.value),
        ]
        async with factory() as session:
            session.add_all(tenants)
            session.add_all([
                TenantMembership(tenant_id=tenant.id, subject=identity, role=role, status=state)
                for tenant, (identity, role, state) in zip(tenants, statuses, strict=True)
            ])
            await session.commit()

        application = create_app(
            Settings(environment="test"),
            credential_verifier=StaticVerifier(
                Principal(subject=subject, principal_type=PrincipalType.USER)
            ),
        )
        application.state.session_factory = factory
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://aegis.test",
        ) as client:
            response = await client.get(
                "/api/v1/me/tenants",
                headers={"Authorization": "Bearer verified-test-token"},
                params={"subject": "oidc|different-user"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "memberships": [{
                "tenant_slug": "northstar-security",
                "display_name": "Northstar Security",
                "role": "tenant_admin",
            }]
        }
        assert "tenant_id" not in payload["memberships"][0]
        assert "membership_id" not in payload["memberships"][0]
        assert "subject" not in payload["memberships"][0]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_returns_an_empty_list_when_subject_has_no_active_membership() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            tenant = Tenant(id=uuid4(), slug="invited-only", display_name="Invited Only")
            session.add(tenant)
            session.add(TenantMembership(
                tenant_id=tenant.id,
                subject="oidc|invitee",
                role="viewer",
                status=MembershipStatus.PENDING.value,
            ))
            await session.commit()

        application = create_app(
            Settings(environment="test"),
            credential_verifier=StaticVerifier(
                Principal(subject="oidc|invitee", principal_type=PrincipalType.USER)
            ),
        )
        application.state.session_factory = factory
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://aegis.test",
        ) as client:
            response = await client.get(
                "/api/v1/me/tenants",
                headers={"Authorization": "Bearer verified-test-token"},
            )

        assert response.status_code == 200
        assert response.json() == {"memberships": []}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_requires_verified_bearer_identity() -> None:
    application = create_app(
        Settings(environment="test"),
        credential_verifier=StaticVerifier(
            Principal(subject="oidc|user", principal_type=PrincipalType.USER)
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://aegis.test",
    ) as client:
        response = await client.get("/api/v1/me/tenants")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_or_missing_credentials"


@pytest.mark.asyncio
async def test_bootstrap_fails_closed_when_membership_store_is_unavailable() -> None:
    application = create_app(
        Settings(environment="test"),
        credential_verifier=StaticVerifier(
            Principal(subject="oidc|user", principal_type=PrincipalType.USER)
        ),
    )
    application.state.session_factory = None
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://aegis.test",
    ) as client:
        response = await client.get(
            "/api/v1/me/tenants",
            headers={"Authorization": "Bearer verified-test-token"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "tenant_membership_store_unavailable"
