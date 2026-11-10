"""PostgreSQL integration tests for tenant membership lifecycle functions."""

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
    reason="PostgreSQL membership integration URLs are not configured",
)


@pytest.mark.asyncio
async def test_membership_lifecycle_and_audit_are_tenant_scoped() -> None:
    admin_engine = create_async_engine(ADMIN_URL)
    provisioner_engine = create_async_engine(PROVISIONER_URL)
    admin_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    provisioner_factory = async_sessionmaker(provisioner_engine, expire_on_commit=False)
    request_id = uuid4()
    slug = f"member-flow-{request_id.hex[:10]}"
    actor = "oidc|tenant-owner"
    invitee = "oidc|new-member"

    try:
        async with provisioner_factory() as session:
            tenant_id = (
                await session.execute(
                    text(
                        """
                        SELECT tenant_id FROM public.aegis_provision_tenant(
                            :slug, 'Membership Flow', :actor, :actor, 'user', :request_id
                        )
                        """
                    ),
                    {"slug": slug, "actor": actor, "request_id": request_id},
                )
            ).scalar_one()
            await session.commit()

        async with provisioner_factory() as session:
            invited = (
                await session.execute(
                    text(
                        """
                        SELECT member_subject, member_role, member_status
                        FROM public.aegis_manage_tenant_member(
                            :tenant_id, :target, 'viewer', 'invite',
                            :actor, 'user', :request_id
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "target": invitee,
                        "actor": actor,
                        "request_id": uuid4(),
                    },
                )
            ).one()
            assert (invited.member_subject, invited.member_role, invited.member_status) == (
                invitee,
                "viewer",
                "pending",
            )
            await session.commit()

        async with provisioner_factory() as session:
            members = (
                await session.execute(
                    text("SELECT * FROM public.aegis_list_tenant_members(:tenant_id, :actor)"),
                    {"tenant_id": tenant_id, "actor": actor},
                )
            ).all()
            assert {row.member_subject for row in members} == {actor, invitee}
            pending = next(row for row in members if row.member_subject == invitee)
            assert pending.member_invitation_expires_at is not None

            accepted = (
                await session.execute(
                    text(
                        """
                        SELECT tenant_id, member_role
                        FROM public.aegis_accept_tenant_invitation(:slug, :actor, :request_id)
                        """
                    ),
                    {"slug": slug, "actor": invitee, "request_id": uuid4()},
                )
            ).one()
            assert accepted.tenant_id == tenant_id
            assert accepted.member_role == "viewer"
            await session.commit()

        for action, role, expected_status in (
            ("change_role", "analyst", "active"),
            ("suspend", None, "suspended"),
            ("revoke", None, "revoked"),
        ):
            async with provisioner_factory() as session:
                changed = (
                    await session.execute(
                        text(
                            """
                            SELECT member_role, member_status
                            FROM public.aegis_manage_tenant_member(
                                :tenant_id, :target, :role, :action,
                                :actor, 'user', :request_id
                            )
                            """
                        ),
                        {
                            "tenant_id": tenant_id,
                            "target": invitee,
                            "role": role,
                            "action": action,
                            "actor": actor,
                            "request_id": uuid4(),
                        },
                    )
                ).one()
                assert changed.member_status == expected_status
                await session.commit()

        # The database itself prevents a sole tenant administrator from being
        # demoted, even if an API caller bypasses its self-change guard.
        async with provisioner_factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(
                    text(
                        """
                        SELECT * FROM public.aegis_manage_tenant_member(
                            :tenant_id, :target, 'viewer', 'change_role',
                            :actor, 'user', :request_id
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "target": actor,
                        "actor": actor,
                        "request_id": uuid4(),
                    },
                )
            await session.rollback()

        async with admin_factory() as session:
            actions = (
                await session.execute(
                    text("SELECT action FROM audit_events WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                )
            ).scalars().all()
            for action in (
                "tenant.member.invite",
                "tenant.member.accept",
                "tenant.member.role_change",
                "tenant.member.suspend",
                "tenant.member.revoke",
            ):
                assert actions.count(action) == 1
    finally:
        await provisioner_engine.dispose()
        await admin_engine.dispose()
