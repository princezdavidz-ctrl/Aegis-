"""Run a complete, resumable NVD CVE catalogue import."""

from __future__ import annotations

import asyncio
import json
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.vulnerability_intel.nvd_sync import sync_nvd_catalogue


async def main() -> None:
    database_url = os.getenv("AEGIS_INGESTOR_DATABASE_URL")
    if not database_url:
        raise RuntimeError("AEGIS_INGESTOR_DATABASE_URL is required")
    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("AEGIS_INGESTOR_DATABASE_URL must use PostgreSQL/asyncpg")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        summary = await sync_nvd_catalogue(
            factory,
            api_key=os.getenv("NVD_API_KEY") or None,
        )
        print(json.dumps(summary, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
