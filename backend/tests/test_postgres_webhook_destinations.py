"""PostgreSQL integration tests for webhook destination KMS boundary and grants."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ADMIN_URL = os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
PROVISIONER_URL = os.getenv("AEGIS_TEST_PROVISIONER_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not ADMIN_URL or not PROVISIONER_URL,
    reason="PostgreSQL webhook integration URLs are not configured",
)


@pytest.mark.asyncio
async def test_webhook_destination_api_function_is_tenant_scoped_and_least_privilege() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    provisioner_engine = create_async_engine(PROVISIONER_URL)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    provisioner_factory = async_sessionmaker(provisioner_engine, expire_on_commit=False)
    request_id = uuid4()
    actor = "oidc|webhook-owner"
    slug = f"webhook-api-{request_id.hex[:10]}"
    destination_id = uuid4()
    try:
        async with provisioner_factory() as session:
            tenant_id = (await session.execute(text("""
                SELECT tenant_id FROM public.aegis_provision_tenant(
                    :slug, 'Webhook API Integration', :actor, :actor, 'user', :request_id)
            """), {"slug": slug, "actor": actor, "request_id": request_id})).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            created = (await session.execute(text("""
                SELECT * FROM public.aegis_webhook_create_destination_v2(
                    :tenant_id, :destination_id, :actor, 'SOC alerts',
                    'https://alerts.example.org/aegis',
                    ARRAY['endpoint.health','endpoint.alert']::text[],
                    :ciphertext, 'kms-test-key', 1, 1)
            """), {
                "tenant_id": tenant_id,
                "destination_id": destination_id,
                "actor": actor,
                "ciphertext": b"X" * 80,
            })).one()
            assert created.destination_id == destination_id
            assert created.status == "active"
            await session.commit()

        async with provisioner_factory() as session:
            listed = (await session.execute(text("""
                SELECT * FROM public.aegis_webhook_list_destinations(:tenant_id, :actor)
            """), {"tenant_id": tenant_id, "actor": actor})).all()
            assert len(listed) == 1
            assert listed[0].destination_id == destination_id
            assert not hasattr(listed[0], "secret_ciphertext")
            assert not hasattr(listed[0], "secret_key_ref")
            await session.commit()

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT * FROM public.aegis_webhook_list_destinations(:tenant_id, 'oidc|other-user')
                """), {"tenant_id": tenant_id})
            await session.rollback()

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT * FROM public.aegis_webhook_create_destination(
                        :tenant_id, :actor, 'Legacy path',
                        'https://alerts.example.org/legacy',
                        ARRAY['endpoint.health']::text[], :ciphertext,
                        'kms-test-key', 1, 1)
                """), {"tenant_id": tenant_id, "actor": actor, "ciphertext": b"Y" * 80})
            await session.rollback()

        async with provisioner_factory() as session:
            disabled = (await session.execute(text("""
                SELECT public.aegis_webhook_disable_destination(
                    :tenant_id, :destination_id, :actor)
            """), {
                "tenant_id": tenant_id,
                "destination_id": destination_id,
                "actor": actor,
            })).scalar_one()
            assert disabled is True
            await session.commit()

        async with provisioner_factory() as session:
            status = (await session.execute(text("""
                SELECT status FROM public.aegis_webhook_list_destinations(:tenant_id, :actor)
                WHERE destination_id = :destination_id
            """), {
                "tenant_id": tenant_id,
                "actor": actor,
                "destination_id": destination_id,
            })).scalar_one()
            assert status == "disabled"
            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT secret_ciphertext FROM public.endpoint_webhook_destinations
                    WHERE tenant_id = :tenant_id
                """), {"tenant_id": tenant_id})
            await session.rollback()

        async with admin_factory() as session:
            # The legacy entry point remains present for rollback but is not executable
            # by the provisioner; the v2 function is the only create capability.
            privileges = (await session.execute(text("""
                SELECT
                    has_function_privilege('aegis_provisioner',
                        'public.aegis_webhook_create_destination_v2(uuid,uuid,text,text,text,text[],bytea,text,smallint,integer)',
                        'EXECUTE') AS can_create_v2,
                    has_function_privilege('aegis_provisioner',
                        'public.aegis_webhook_create_destination(uuid,text,text,text,text[],bytea,text,smallint,integer)',
                        'EXECUTE') AS can_create_legacy
            """))).one()
            assert privileges.can_create_v2 is True
            assert privileges.can_create_legacy is False
    finally:
        await provisioner_engine.dispose()
        await admin_engine.dispose()
