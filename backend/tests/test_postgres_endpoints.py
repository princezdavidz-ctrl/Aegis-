"""PostgreSQL integration tests for endpoint enrollment, telemetry and fleet isolation."""
from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ADMIN_URL = os.getenv("AEGIS_TEST_ADMIN_DATABASE_URL")
PROVISIONER_URL = os.getenv("AEGIS_TEST_PROVISIONER_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not ADMIN_URL or not PROVISIONER_URL,
    reason="PostgreSQL endpoint integration URLs are not configured",
)


@pytest.mark.asyncio
async def test_endpoint_lifecycle_is_single_use_signed_tenant_scoped_and_audited() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    provisioner_engine = create_async_engine(PROVISIONER_URL)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    provisioner_factory = async_sessionmaker(provisioner_engine, expire_on_commit=False)
    request_id = uuid4()
    actor = "oidc|endpoint-owner"
    slug = f"endpoint-flow-{request_id.hex[:10]}"
    token = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    public_b64 = base64.b64encode(public).decode("ascii")
    fingerprint = hashlib.sha256(public).hexdigest()
    try:
        async with provisioner_factory() as session:
            tenant_id = (await session.execute(text("""
                SELECT tenant_id FROM public.aegis_provision_tenant(
                    :slug,'Endpoint Flow',:actor,:actor,'user',:request_id)
            """), {"slug":slug,"actor":actor,"request_id":request_id})).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            invitation = (await session.execute(text("""
                SELECT invitation_id FROM public.aegis_endpoint_create_invitation(
                    :tenant_id,:actor,'user',:request_id,:digest,'linux',:expires_at)
            """), {"tenant_id":tenant_id,"actor":actor,"request_id":uuid4(),"digest":digest,
                "expires_at":datetime.now(timezone.utc)+timedelta(minutes=30)})).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            enrolled = (await session.execute(text("""
                SELECT device_id,tenant_id FROM public.aegis_endpoint_redeem_invitation(
                    :digest,'linux',:public_key_b64,:fingerprint,'sensor-01','0.1.0')
            """), {"digest":digest,"public_key_b64":public_b64,"fingerprint":fingerprint})).one()
            device_id = enrolled.device_id
            assert enrolled.tenant_id == tenant_id
            await session.commit()

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT * FROM public.aegis_endpoint_redeem_invitation(
                        :digest,'linux',:public_key_b64,:fingerprint,'sensor-01','0.1.0')
                """), {"digest":digest,"public_key_b64":public_b64,"fingerprint":fingerprint})
            await session.rollback()

        async with provisioner_factory() as session:
            active_key = (await session.execute(text("""
                SELECT public_key_b64 FROM public.aegis_endpoint_get_active_key(:device_id)
            """), {"device_id":device_id})).scalar_one()
            assert active_key == public_b64
            accepted = (await session.execute(text("""
                SELECT event_id,sequence FROM public.aegis_endpoint_accept_event(
                    :device_id,1,:event_id,'heartbeat',:observed_at,CAST(:payload AS jsonb))
            """), {"device_id":device_id,"event_id":uuid4(),
                "observed_at":datetime.now(timezone.utc),"payload":'{"status":"healthy"}'})).one()
            assert accepted.sequence == 1
            await session.commit()

        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT * FROM public.aegis_endpoint_accept_event(
                        :device_id,1,:event_id,'heartbeat',:observed_at,CAST(:payload AS jsonb))
                """), {"device_id":device_id,"event_id":uuid4(),
                    "observed_at":datetime.now(timezone.utc),"payload":'{"status":"replay"}'})
            await session.rollback()

        async with provisioner_factory() as session:
            rows = (await session.execute(text("""
                SELECT device_id,platform,hostname,status,last_sequence,last_event_type
                FROM public.aegis_endpoint_list_devices(:tenant_id,:actor,100)
            """), {"tenant_id":tenant_id,"actor":actor})).all()
            assert len(rows) == 1
            assert (rows[0].device_id,rows[0].platform,rows[0].hostname,
                rows[0].status,rows[0].last_sequence,rows[0].last_event_type) == (
                    device_id,"linux","sensor-01","active",1,"heartbeat")
            await session.commit()

        async with provisioner_factory() as session:
            await session.execute(text("""
                SELECT public.aegis_endpoint_revoke_device(
                    :tenant_id,:device_id,:actor,'user',:request_id)
            """), {"tenant_id":tenant_id,"device_id":device_id,"actor":actor,"request_id":uuid4()})
            await session.commit()

        async with provisioner_factory() as session:
            # The provisioner has no direct table grants; verify through the inventory function.
            rows = (await session.execute(text("""
                SELECT status FROM public.aegis_endpoint_list_devices(:tenant_id,:actor,100)
            """), {"tenant_id":tenant_id,"actor":actor})).scalars().all()
            assert rows == ["revoked"]

            with pytest.raises(DBAPIError):
                await session.execute(text("""
                    SELECT * FROM public.aegis_endpoint_accept_event(
                        :device_id,2,:event_id,'heartbeat',:observed_at,CAST(:payload AS jsonb))
                """), {"device_id":device_id,"event_id":uuid4(),
                    "observed_at":datetime.now(timezone.utc),"payload":'{"status":"must-reject"}'})
            await session.rollback()

        async with admin_factory() as session:
            actions = (await session.execute(text("""
                SELECT action FROM audit_events
                WHERE tenant_id=:tenant_id AND resource_type IN ('endpoint_invitation','endpoint_device')
            """), {"tenant_id":tenant_id})).scalars().all()
            assert actions.count("endpoint.invitation.create") == 1
            assert actions.count("endpoint.enroll") == 1
            assert actions.count("endpoint.revoke") == 1
    finally:
        await provisioner_engine.dispose()
        await admin_engine.dispose()
