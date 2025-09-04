"""
macOS Platform Router

Aggregates all macOS-specific routers into a single router for the platform.
"""

from fastapi import APIRouter

from .routers.actions import router as actions_router
from .routers.camera import router as camera_router
from .routers.camguard import router as camguard_router
from .routers.health import router as health_router
from .routers.tracker import router as tracker_router

# Create main router for macOS platform
router = APIRouter(
    prefix="/macos",
    tags=["macOS Platform"]
)

# Include all platform-specific routers
router.include_router(health_router, tags=["Health"])
router.include_router(actions_router, tags=["Actions"])
router.include_router(camera_router, tags=["Camera"])
router.include_router(camguard_router, tags=["CamGuard"])
router.include_router(tracker_router, tags=["Tracker"])
