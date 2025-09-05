"""
Unified Device API Entry Point

Automatically detects platform and loads appropriate routers and services.
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.oaDeviceAPI.core.caching import setup_cache
from src.oaDeviceAPI.core.config import APP_VERSION, app_config

# Configure logging
from src.oaDeviceAPI.core.logging import RequestTrackingMiddleware, setup_logging
from src.oaDeviceAPI.core.platform import platform_manager
from src.oaDeviceAPI.middleware import TailscaleSubnetMiddleware

logging_manager = setup_logging(app_config)
cache_manager = setup_cache(app_config)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        f"Starting oaDeviceAPI v{APP_VERSION}",
        extra={
            "platform": platform_manager.platform,
            "features": platform_manager.get_available_features(),
            "event_type": "startup"
        }
    )

    # Warm cache if enabled
    if cache_manager and app_config.cache.enable_caching:
        logger.info("Cache warming started")
        # Add cache warming logic here if needed

    yield

    logger.info("Shutting down oaDeviceAPI", extra={"event_type": "shutdown"})


# Create FastAPI application
app = FastAPI(
    title="OrangeAd Device API",
    description="Unified API for device management across macOS and OrangePi platforms",
    version=APP_VERSION,
    lifespan=lifespan
)

# Configure middleware
app.add_middleware(RequestTrackingMiddleware)

# Add CORS middleware if enabled
if app_config.security.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_config.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add Tailscale subnet restriction if enabled
if app_config.security.enable_tailscale_restriction:
    app.add_middleware(
        TailscaleSubnetMiddleware,
        tailscale_subnet_str=app_config.network.tailscale_subnet
    )

# Platform-specific router loading
if platform_manager.is_macos():
    from src.oaDeviceAPI.platforms.macos.router import router as macos_router
    app.include_router(macos_router)
    logger.info("Loaded macOS platform routers")
elif platform_manager.is_orangepi():
    from src.oaDeviceAPI.platforms.orangepi.router import router as orangepi_router
    app.include_router(orangepi_router)
    logger.info("Loaded OrangePi platform routers")
else:
    # Fallback for generic Linux
    from src.oaDeviceAPI.platforms.orangepi.router import router as linux_router
    app.include_router(linux_router)
    logger.info("Loaded generic Linux platform routers")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "oaDeviceAPI",
        "version": APP_VERSION,
        "platform": platform_manager.platform,
        "features": platform_manager.get_available_features(),
        "endpoints": {
            "health": "/health",
            "platform": "/",  # Root endpoint provides platform info
            "system": "/system", 
            "docs": "/docs"
        }
    }

# Generic health endpoint for deployment validation
@app.get("/health")
async def health():
    """Generic health check endpoint that works across all platforms."""
    return {
        "status": "healthy",
        "platform": platform_manager.platform,
        "version": APP_VERSION,
        "timestamp": platform_manager.get_current_time(),
        "detailed_health": f"/{platform_manager.platform}/health"
    }

if __name__ == "__main__":
    # Configure uvicorn server
    uvicorn.run(
        "main:app",
        host=app_config.network.host,
        port=app_config.network.port,
        log_level=app_config.logging.level.value.lower(),
        reload=app_config.is_development(),
        access_log=True
    )
