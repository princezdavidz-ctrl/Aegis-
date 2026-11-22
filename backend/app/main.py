"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from aegis_ai.config import AISettings
from aegis_ai.gateway import ModelGateway
from aegis_ai.providers.openai_compatible import OpenAICompatibleProvider

from app.ai.knowledge_config import KnowledgeSettings
from app.ai.knowledge_runtime import build_knowledge_runtime, verify_database_role
from app.ai.specialist_service import SpecialistAnalysisAdapter
from app.api.ai_analysis import router as ai_analysis_router
from app.api.assets import router as assets_router
from app.api.endpoints import router as endpoint_router
from app.api.memberships import router as membership_router
from app.api.membership_bootstrap import router as membership_bootstrap_router
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
        engines = []
        ai_provider = None
        application.state.session_factory = None
        application.state.provisioner_session_factory = None
        application.state.knowledge_runtime = None
        application.state.ai_provider = None
        application.state.specialist_analysis_service = None

        try:
            knowledge_settings = KnowledgeSettings.from_environment(
                environment=resolved_settings.environment
            )
            if (
                knowledge_settings.enabled
                and knowledge_settings.embedding_provider != "openai-compatible"
            ):
                raise RuntimeError("configured knowledge embedding provider is unsupported")

            if resolved_settings.database_url is not None:
                engine, factory = create_session_factory(
                    resolved_settings.database_url.get_secret_value()
                )
                engines.append(engine)
                application.state.session_factory = factory

            if resolved_settings.provisioner_database_url is not None:
                provisioner_engine, provisioner_factory = create_session_factory(
                    resolved_settings.provisioner_database_url.get_secret_value()
                )
                engines.append(provisioner_engine)
                application.state.provisioner_session_factory = provisioner_factory

            if knowledge_settings.enabled:
                runtime_url = knowledge_settings.runtime_database_url
                ingestor_url = knowledge_settings.ingestor_database_url
                if runtime_url is None or ingestor_url is None:
                    raise RuntimeError("knowledge memory configuration is incomplete")

                runtime_engine, runtime_factory = create_session_factory(
                    runtime_url.get_secret_value()
                )
                engines.append(runtime_engine)
                ingestor_engine, ingestor_factory = create_session_factory(
                    ingestor_url.get_secret_value()
                )
                engines.append(ingestor_engine)

                await verify_database_role(
                    runtime_factory,
                    expected_role="aegis_runtime",
                )
                await verify_database_role(
                    ingestor_factory,
                    expected_role="aegis_ingestor",
                )
                application.state.knowledge_runtime = build_knowledge_runtime(
                    knowledge_settings,
                    runtime_session_factory=runtime_factory,
                    ingestor_session_factory=ingestor_factory,
                )

            ai_settings = AISettings.from_environment()
            if ai_settings.model != "unset" and ai_settings.api_key:
                ai_provider = OpenAICompatibleProvider(ai_settings)
                application.state.ai_provider = ai_provider
                application.state.specialist_analysis_service = SpecialistAnalysisAdapter(
                    ModelGateway(ai_provider)
                )
            yield
        finally:
            application.state.knowledge_runtime = None
            try:
                if ai_provider is not None:
                    await ai_provider.aclose()
            finally:
                for engine in reversed(engines):
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
    application.include_router(membership_bootstrap_router)
    application.include_router(tenant_profile_router)
    application.include_router(assets_router)
    application.include_router(endpoint_router)
    return application


app = create_app()
