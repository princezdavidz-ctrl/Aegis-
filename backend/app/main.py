"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from aegis_ai.config import AISettings
from aegis_ai.gateway import ModelGateway
from aegis_ai.providers.openai_compatible import OpenAICompatibleProvider

from app.ai.specialist_service import SpecialistAnalysisAdapter
from app.api.ai_analysis import router as ai_analysis_router
from app.api.assets import router as assets_router
from app.api.memberships import router as membership_router
from app.api.tenants import router as tenant_router
from app.api.tenant_profile import router as tenant_profile_router
from app.config import Settings
from app.db.session import create_session_factory
from app.health import router as health_router
from app.security.authentication import CredentialVerifier
from app.security.oidc import OidcJwtCredentialVerifier


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
    """Build an independently testable AEGIS API application."""

    resolved_settings = settings or Settings.from_environment()
    configure_logging(resolved_settings.log_level)

    resolved_verifier = credential_verifier
    if (
        resolved_verifier is None
        and resolved_settings.oidc_issuer
        and resolved_settings.oidc_audience
        and resolved_settings.oidc_jwks_url
    ):
        resolved_verifier = OidcJwtCredentialVerifier(
            issuer=resolved_settings.oidc_issuer,
            audience=resolved_settings.oidc_audience,
            jwks_url=resolved_settings.oidc_jwks_url,
            clock_skew_seconds=resolved_settings.oidc_clock_skew_seconds,
            jwks_cache_seconds=resolved_settings.oidc_jwks_cache_seconds,
            allow_loopback_http=resolved_settings.environment in {"development", "test"},
        )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = None
        provisioner_engine = None
        ai_provider = None
        application.state.session_factory = None
        application.state.provisioner_session_factory = None
        application.state.ai_provider = None
        application.state.specialist_analysis_service = None
        if resolved_settings.database_url is not None:
            engine, factory = create_session_factory(
                resolved_settings.database_url.get_secret_value()
            )
            application.state.session_factory = factory
        if resolved_settings.provisioner_database_url is not None:
            provisioner_engine, provisioner_factory = create_session_factory(
                resolved_settings.provisioner_database_url.get_secret_value()
            )
            application.state.provisioner_session_factory = provisioner_factory
        ai_settings = AISettings.from_environment()
        if ai_settings.model != "unset" and ai_settings.api_key:
            ai_provider = OpenAICompatibleProvider(ai_settings)
            application.state.ai_provider = ai_provider
            application.state.specialist_analysis_service = SpecialistAnalysisAdapter(
                ModelGateway(ai_provider)
            )
        try:
            yield
        finally:
            if ai_provider is not None:
                await ai_provider.aclose()
            if provisioner_engine is not None:
                await provisioner_engine.dispose()
            if engine is not None:
                await engine.dispose()

    is_production = resolved_settings.environment == "production"
    application = FastAPI(
        title=resolved_settings.app_name,
        version="0.4.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.credential_verifier = resolved_verifier
    application.include_router(health_router)
    application.include_router(ai_analysis_router)
    application.include_router(tenant_router)
    application.include_router(membership_router)
    application.include_router(tenant_profile_router)
    application.include_router(assets_router)
    return application


app = create_app()
