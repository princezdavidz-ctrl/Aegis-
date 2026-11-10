"""Run a complete, resumable NVD CVE catalogue import."""

from __future__ import annotations

import asyncio
import json
import os

from app.vulnerability_intel.nvd_sync import sync_nvd_catalogue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def main() -> None:
    database_url = os.getenv("AEGIS_INGESTOR_DATABASE_URL")
    if not database_url:
        raise RuntimeError("AEGIS_INGESTOR_DATABASE_URL is required")
    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("AEGIS_INGESTOR_DATABASE_URL must use PostgreSQL/asyncpg")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        summary = await sync_nvd_catalogue(factory)
        async with factory() as session:
            summary["catalogue_total"] = await session.scalar(
                text("SELECT count(*) FROM public.cve_catalog")
            )
            summary["completed_feed_count"] = await session.scalar(
                text("SELECT count(*) FROM public.nvd_feed_sync")
            )
        print(json.dumps(summary, indent=2, default=str))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
