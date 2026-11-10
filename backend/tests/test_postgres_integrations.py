"""PostgreSQL integration tests for integration authorization and tenant RLS."""
from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import AuditRecord, Integration
from app.db.session import apply_database_context

ADMIN_URL = os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
RUNTIME_URL = os.getenv("AEGIS_TEST_DATABASE_URL")
PROVISIONER_URL = os.getenv("AEGIS_TEST_PROVISIONER_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not ADMIN_URL or not RUNTIME_URL or not PROVISIONER_URL,
    reason="PostgreSQL integration authorization test URLs are not configured",
)


@pytest.mark.asyncio
async def test_integration_request_requires_approval_and_never_auto_activates() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    runtime_engine = create_async_engine(RUNTIME_URL)
    provisioner_engine = create_async_engine(PROVISIONER_URL)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    runtime_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    provisioner_factory = async_sessionmaker(provisioner_engine, expire_on_commit=False)
    actor = "oidc|integration-admin"
    slug = f"connect-{uuid4().hex[:10]}"

    try:
        async with provisioner_factory() as session:
            tenant_id = (
                await session.execute(
                    text(
                        """
                        SELECT tenant_id FROM public.aegis_provision_tenant(
                            :slug, 'Integration Test', :actor, :actor, 'user', :request_id
                        )
                        """
                    ),
                    {"slug": slug, "actor": actor, "request_id": uuid4()},
                )
            ).scalar_one()
            tenant_b = (
                await session.execute(
                    text(
                        """
                        SELECT tenant_id FROM public.aegis_provision_tenant(
                            :slug, 'Other Integration Tenant',
                            'oidc|other-admin', 'oidc|other-admin', 'user', :request_id
                        )
                        """
                    ),
                    {"slug": f"{slug}-b", "request_id": uuid4()},
                )
            ).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            privileges = (
                await session.execute(
                    text(
                        """
                        SELECT has_table_privilege(current_user, 'integrations', 'SELECT'),
                               has_table_privilege(current_user, 'integrations', 'INSERT'),
                               has_table_privilege(current_user, 'integrations', 'UPDATE')
                        """
                    )
                )
            ).one()
            assert privileges == (False, False, False)

            row = (
                await session.execute(
                    text(
                        """
                        SELECT integration_id, integration_status, integration_access_mode,
                               integration_requested_scopes
                        FROM public.aegis_request_integration(
                            :tenant_id, :actor, 'user', :request_id, 'github',
                            'GitHub Org', 'acme-org', CAST(:scopes AS json)
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "actor": actor,
                        "request_id": uuid4(),
                        "scopes": json.dumps(["repositories:read", "alerts:read"]),
                    },
                )
            ).one()
            assert row.integration_status == "requested"
            assert row.integration_access_mode == "read_only"
            assert row.integration_requested_scopes == ["repositories:read", "alerts:read"]
            integration_id = row.integration_id
            await session.commit()

        async with runtime_factory() as session:
            await apply_database_context(session, subject=actor, tenant_id=tenant_id)
            items = (
                await session.execute(
                    select(Integration).where(Integration.tenant_id == tenant_id)
                )
            ).scalars().all()
            assert len(items) == 1
            assert items[0].id == integration_id
            assert items[0].status == "requested"

        async with runtime_factory() as session:
            # Even with the other tenant's UUID supplied as context, this
            # subject has no active membership there and sees no integrations.
            await apply_database_context(session, subject=actor, tenant_id=tenant_b)
            other_rows = (await session.execute(select(Integration))).scalars().all()
            assert other_rows == []

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(
                    text(
                        """
                        SELECT * FROM public.aegis_approve_integration(
                            :tenant_id, :integration_id, :actor,
                            CAST(:scopes AS json), :request_id
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "integration_id": integration_id,
                        "actor": actor,
                        "scopes": json.dumps(["config:read"]),
                        "request_id": uuid4(),
                    },
                )
            await session.rollback()

        async with provisioner_factory() as session:
            approved = (
                await session.execute(
                    text(
                        """
                        SELECT integration_status, integration_approved_scopes
                        FROM public.aegis_approve_integration(
                            :tenant_id, :integration_id, :actor,
                            CAST(:scopes AS json), :request_id
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "integration_id": integration_id,
                        "actor": actor,
                        "scopes": json.dumps(["repositories:read"]),
                        "request_id": uuid4(),
                    },
                )
            ).one()
            assert approved.integration_status == "approved_pending_verification"
            assert approved.integration_approved_scopes == ["repositories:read"]
            await session.commit()

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(
                    text(
                        """
                        SELECT * FROM public.aegis_approve_integration(
                            :tenant_id, :integration_id, :actor,
                            CAST(:scopes AS json), :request_id
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "integration_id": integration_id,
                        "actor": actor,
                        "scopes": json.dumps(["alerts:read"]),
                        "request_id": uuid4(),
                    },
                )
            await session.rollback()

        async with provisioner_factory() as session:
            revoked = (
                await session.execute(
                    text(
                        """
                        SELECT integration_status FROM public.aegis_revoke_integration(
                            :tenant_id, :integration_id, :actor, :request_id
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "integration_id": integration_id,
                        "actor": actor,
                        "request_id": uuid4(),
                    },
                )
            ).scalar_one()
            assert revoked == "revoked"
            await session.commit()

        async with admin_factory() as session:
            actions = (
                await session.execute(
                    select(AuditRecord.action).where(
                        AuditRecord.tenant_id == tenant_id,
                        AuditRecord.resource_type == "integration",
                    )
                )
            ).scalars().all()
            assert actions.count("integration.request") == 1
            assert actions.count("integration.approve") == 1
            assert actions.count("integration.revoke") == 1
    finally:
        await provisioner_engine.dispose()
        await runtime_engine.dispose()
        await admin_engine.dispose()
