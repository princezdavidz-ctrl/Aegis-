"""Versioned API router composition.

Only health routes are registered by the current application. Feature routers
must be added here only after their authentication, tenant-scope, authorization,
and durable-audit requirements are implemented and tested.
"""

from fastapi import APIRouter

api_router = APIRouter()
