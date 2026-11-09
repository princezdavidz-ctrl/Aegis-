"""Unauthenticated, non-sensitive process health endpoints."""

from fastapi import APIRouter, Request

from app.config import Settings
from app.schemas import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Report that the ASGI process can accept and answer requests."""

    return LivenessResponse()


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> ReadinessResponse:
    """Report API readiness without implying external services are connected."""

    settings: Settings = request.app.state.settings
    return ReadinessResponse(
        service=settings.app_name,
        environment=settings.environment,
        checks={
            "application": "ready",
            "external_dependencies": "not_configured",
        },
    )
