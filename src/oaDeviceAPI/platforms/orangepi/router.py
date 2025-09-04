"""
OrangePi Platform Router

Aggregates all OrangePi-specific routers into a single router for the platform.
"""

from fastapi import APIRouter

from .routers.actions import router as actions_router
from .routers.health import router as health_router
from .routers.screenshots import router as screenshots_router

# Create main router for OrangePi platform
router = APIRouter(
    prefix="/orangepi",
    tags=["OrangePi Platform"]
)

# Include all platform-specific routers
router.include_router(health_router, tags=["Health"])
router.include_router(actions_router, tags=["Actions"])
router.include_router(screenshots_router, tags=["Screenshots"])
