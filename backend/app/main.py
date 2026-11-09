"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import Settings
from app.health import router as health_router
from app.security.authentication import CredentialVerifier


def configure_logging(level: str) -> None:
    """Configure concise process logging without recording request payloads."""

    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(
    settings: Settings | None = None,
    *,
    credential_verifier: CredentialVerifier | None = None,
) -> FastAPI:
    """Build an independently testable AEGIS API application.

    A verifier may be injected by a trusted deployment adapter. No verifier is
    configured by default, and no protected route is registered at this stage.
    """

    resolved_settings = settings or Settings.from_environment()
    configure_logging(resolved_settings.log_level)

    is_production = resolved_settings.environment == "production"
    application = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    application.state.settings = resolved_settings
    application.state.credential_verifier = credential_verifier
    application.include_router(health_router)
    return application


app = create_app()
