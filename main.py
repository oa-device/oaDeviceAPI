"""
Unified Device API Entry Point

Automatically detects platform and loads appropriate routers and services.
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.oaDeviceAPI.core.config import APP_VERSION, settings
from src.oaDeviceAPI.core.platform import platform_manager
from src.oaDeviceAPI.middleware import TailscaleSubnetMiddleware

# Configure logging
from src.oaDeviceAPI.core.logging import setup_logging, RequestTrackingMiddleware
from src.oaDeviceAPI.core.caching import setup_cache
logging_manager = setup_logging(settings)
cache_manager = setup_cache(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        f"Starting oaDeviceAPI v{APP_VERSION}",
        extra={
            "event_type": "application_start",
            "version": APP_VERSION,
            "platform": platform_manager.platform,
            "features": platform_manager.get_available_features()
        }
    )
    
    # Platform-specific setup
    if platform_manager.is_orangepi() and platform_manager.supports_feature("screenshot"):
        # Ensure screenshot directory exists
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Screenshot directory created: {settings.screenshot_dir}")
    
    yield
    
    logger.info("Shutting down oaDeviceAPI")


# Initialize FastAPI app
app = FastAPI(
    title="OrangeAd Unified Device API",
    version=APP_VERSION,
    description="Unified device management API for macOS and OrangePi devices",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request tracking middleware (first)
app.add_middleware(RequestTrackingMiddleware)

# Add error handling middleware (before other middleware)
from src.oaDeviceAPI.core.error_handler import ErrorHandlingMiddleware
app.add_middleware(ErrorHandlingMiddleware, include_traceback=settings.dev.include_traceback)

# Add Tailscale subnet restriction middleware
app.add_middleware(TailscaleSubnetMiddleware, tailscale_subnet_str=settings.tailscale_subnet)

# Load platform-specific routers
if platform_manager.is_macos():
    logger.info("Loading macOS-specific routers")
    try:
        from src.oaDeviceAPI.platforms.macos.routers import (
            health as macos_health,
            camera as macos_camera, 
            actions as macos_actions,
            tracker as macos_tracker,
            camguard as macos_camguard,
        )
        
        app.include_router(macos_health.router, tags=["health"])
        app.include_router(macos_camera.router, tags=["camera"])
        app.include_router(macos_actions.router, tags=["actions"]) 
        app.include_router(macos_tracker.router, tags=["tracker"])
        app.include_router(macos_camguard.router, tags=["camguard"])
        
        logger.info("macOS routers loaded successfully")
    except ImportError as e:
        logger.error(f"Failed to load macOS routers: {e}")

elif platform_manager.is_orangepi():
    logger.info("Loading OrangePi-specific routers")
    try:
        from src.oaDeviceAPI.platforms.orangepi.routers import (
            health as orangepi_health,
            screenshots as orangepi_screenshots,
            actions as orangepi_actions,
        )
        
        app.include_router(orangepi_health.router, tags=["health"])
        app.include_router(orangepi_screenshots.router, tags=["screenshots"])
        app.include_router(orangepi_actions.router, tags=["actions"])
        
        logger.info("OrangePi routers loaded successfully")
    except ImportError as e:
        logger.error(f"Failed to load OrangePi routers: {e}")

else:
    logger.warning(f"Unknown or unsupported platform: {platform_manager.platform}")
    logger.info("Loading minimal generic routers")
    
    # Load generic health router as fallback
    try:
        from src.oaDeviceAPI.routers import health as generic_health
        app.include_router(generic_health.router, tags=["health"])
        logger.info("Generic health router loaded")
    except ImportError as e:
        logger.error(f"Failed to load generic router: {e}")


@app.get("/")
async def root():
    """Root endpoint with API information and platform details."""
    platform_info = platform_manager.get_platform_info()
    
    # Build endpoint information based on available features
    endpoints = {
        "platform": "/platform",
        "health": "/health",
        "health_summary": "/health/summary",
    }
    
    if platform_manager.supports_feature("camera"):
        endpoints.update({
            "cameras": {
                "list": "/cameras",
                "status": "/cameras/status", 
                "stream": "/cameras/{camera_id}/stream",
            }
        })
    
    if platform_manager.supports_feature("screenshot"):
        endpoints.update({
            "screenshots": {
                "capture": "/screenshots/capture",
                "latest": "/screenshots/latest",
                "history": "/screenshots/history"
            }
        })
    
    if platform_manager.supports_feature("tracker"):
        endpoints.update({
            "tracker": {
                "stats": "/tracker/stats",
                "status": "/tracker/status",
                "stream": "/tracker/stream",
                "mjpeg": "/tracker/mjpeg",
            }
        })
    
    if platform_manager.supports_feature("camguard"):
        endpoints.update({
            "camguard": {
                "status": "/camguard/status",
                "stream_url": "/camguard/stream_url",
                "recordings": "/camguard/recordings",
                "storage": "/camguard/storage",
                "restart": "/camguard/actions/restart",
                "cleanup": "/camguard/actions/cleanup",
            }
        })
    
    # Add action endpoints
    actions = {"reboot": "/actions/reboot"}
    if platform_manager.supports_feature("tracker"):
        actions["restart_tracker"] = "/actions/restart-tracker"
    if platform_manager.supports_feature("screenshot"):
        actions["restart_player"] = "/actions/restart-player"
    
    endpoints["actions"] = actions
    
    return {
        "name": "OrangeAd Unified Device API",
        "version": APP_VERSION,
        "status": "running",
        "platform": platform_info,
        "endpoints": endpoints,
    }


@app.get("/platform")
async def platform_info():
    """Get detailed platform information."""
    return platform_manager.get_platform_info()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # For development
        log_level=settings.log_level.lower()
    )