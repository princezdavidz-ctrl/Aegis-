"""Async SQLAlchemy engine and session factory construction."""

from __future__ import annotations

from collections.abc import AsyncIterator

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


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one request-scoped session; never share sessions across requests."""

    async with factory() as session:
        yield session
