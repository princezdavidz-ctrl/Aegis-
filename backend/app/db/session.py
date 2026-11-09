"""Async SQLAlchemy engine, request sessions and PostgreSQL RLS context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_session_factory(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an async engine and session factory; callers own engine disposal."""

    if not database_url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
        raise ValueError("database_url must use PostgreSQL/asyncpg or SQLite/aiosqlite")
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def apply_database_context(
    session: AsyncSession,
    *,
    subject: str,
    tenant_id: UUID | None = None,
) -> None:
    """Set transaction-local values consumed by PostgreSQL RLS policies."""

    # SQLite is used only for isolated unit tests; production is PostgreSQL.
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT set_config('aegis.subject', :subject, true)"),
        {"subject": subject},
    )
    if tenant_id is not None:
        await session.execute(
            text("SELECT set_config('aegis.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one request-scoped session; never share sessions across requests."""

    async with factory() as session:
        yield session
