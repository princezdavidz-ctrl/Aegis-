"""Unit tests for the webhook destination repository boundary."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories.webhook_destinations import (
    create_webhook_destination,
    disable_webhook_destination,
    list_webhook_destinations,
)


class FakeSession:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.committed = False

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return self.result

    async def commit(self):
        self.committed = True


class FakeFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        @asynccontextmanager
        async def manager():
            yield self.session
        return manager()


@pytest.mark.asyncio
async def test_create_passes_ciphertext_only_and_returns_no_secret_material():
    destination_id = uuid4()
    created_at = datetime.now(timezone.utc)
    row = SimpleNamespace(
        destination_id=destination_id, name="SOC alerts",
        target_url="https://alerts.example.org/aegis",
        status="active", event_types=["endpoint.health"],
        secret_version=1, created_at=created_at,
    )
    session = FakeSession(SimpleNamespace(one=lambda: row))
    factory = FakeFactory(session)
    ciphertext = b"\x01" * 128

    result = await create_webhook_destination(
        factory, tenant_id=uuid4(), destination_id=destination_id, actor="security-admin",
        name="SOC alerts", target_url="https://alerts.example.org/aegis",
        event_types=["endpoint.health"], secret_ciphertext=ciphertext,
        secret_key_ref="arn:aws:kms:region:account:key/id",
    )

    assert result["id"] == destination_id
    assert "secret_ciphertext" not in result
    assert "secret_key_ref" not in result
    assert session.calls[0][1]["destination_id"] == destination_id
    assert "aegis_webhook_create_destination_v2" in session.calls[0][0]
    assert session.calls[0][1]["secret_ciphertext"] == ciphertext
    assert session.committed


@pytest.mark.asyncio
async def test_list_never_selects_or_returns_ciphertext():
    row = SimpleNamespace(
        destination_id=uuid4(), name="SOC alerts",
        target_url="https://alerts.example.org/aegis", status="active",
        event_types=["endpoint.health"], secret_version=2,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        disabled_at=None,
    )

    class RowsResult:
        def all(self):
            return [row]

    session = FakeSession(RowsResult())
    result = await list_webhook_destinations(
        FakeFactory(session), tenant_id=uuid4(), actor="security-admin",
    )

    assert len(result) == 1
    assert "secret_ciphertext" not in result[0]
    assert "secret_key_ref" not in result[0]
    assert "aegis_webhook_list_destinations" in session.calls[0][0]


@pytest.mark.asyncio
async def test_disable_is_tenant_scoped_and_commits():
    class ScalarResult:
        def scalar_one(self):
            return True

    session = FakeSession(ScalarResult())
    tenant_id, destination_id = uuid4(), uuid4()
    changed = await disable_webhook_destination(
        FakeFactory(session), tenant_id=tenant_id,
        destination_id=destination_id, actor="security-admin",
    )

    assert changed is True
    assert session.calls[0][1] == {
        "tenant_id": tenant_id, "destination_id": destination_id,
        "actor": "security-admin",
    }
    assert session.committed
