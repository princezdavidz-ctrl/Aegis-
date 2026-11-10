"""Durable append-only SQLAlchemy audit sink."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AuditRecord
from app.db.session import apply_database_context
from app.security.audit import AuditEvent


class PostgresAuditEventSink:
    """Persist payload-free audit events; write failures propagate to caller.

    This adapter exposes append only. The migration also installs a PostgreSQL
    trigger that rejects update/delete; runtime grants must remain least-privilege.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, event: AuditEvent, /) -> None:
        if event.tenant_id is None:
            raise ValueError("audit event requires a resolved tenant_id")
        record = AuditRecord(
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            occurred_at=event.occurred_at,
            actor_subject=event.actor_subject,
            actor_type=event.actor_type.value,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            outcome=event.outcome.value,
            authorization_reason=event.authorization_reason.value,
            correlation_id=event.correlation_id,
        )
        async with self._session_factory() as session:
            await apply_database_context(
                session, subject=event.actor_subject, tenant_id=event.tenant_id
            )
            session.add(record)
            # A failure is not swallowed: protected actions must fail closed.
            await session.commit()
