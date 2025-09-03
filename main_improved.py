"""
Improved Unified Device API Entry Point with Dependency Injection.

Automatically detects platform and loads appropriate routers and services
using the dependency injection container for better testability and maintainability.
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Core imports
from src.oaDeviceAPI.core.config import APP_VERSION, settings
from src.oaDeviceAPI.core.platform import platform_manager
from src.oaDeviceAPI.core.bootstrap import initialize_application, inject_services, get_bootstrap_info
from src.oaDeviceAPI.core.interfaces import HealthServiceInterface, MetricsCollectorInterface
from src.oaDeviceAPI.core.unified_metrics import MetricsFacade
from src.oaDeviceAPI.middleware import TailscaleSubnetMiddleware

# Error handling and logging
from src.oaDeviceAPI.core.logging import setup_logging, RequestTrackingMiddleware
from src.oaDeviceAPI.core.error_handler import ErrorHandlingMiddleware
from src.oaDeviceAPI.core.caching import setup_cache
from src.oaDeviceAPI.core.exceptions import ServiceError, ErrorSeverity

# Initialize logging and caching
logging_manager = setup_logging(settings)
cache_manager = setup_cache(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with dependency injection setup."""
    logger.info("Starting oaDeviceAPI with improved architecture...")
    
    try:
        # Initialize dependency injection container
        container = initialize_application(platform_manager)
        
        # Store container in app state for access in routes
        app.state.container = container
        
        # Get bootstrap information
        bootstrap_info = get_bootstrap_info()
        
        logger.info(
            f"oaDeviceAPI v{APP_VERSION} started successfully",
            extra={
                "event_type": "application_start",
                "version": APP_VERSION,
                "platform": platform_manager.platform,
                "features": platform_manager.get_available_features(),
                "services_registered": bootstrap_info['service_count'],
                "architecture": "dependency_injection"
            }
        )
        
        # Platform-specific setup
        await _setup_platform_specific_features()
        
        # Validate core services
        await _validate_core_services(container)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise

    yield
    
    logger.info("Shutting down oaDeviceAPI")


async def _setup_platform_specific_features():
    """Setup platform-specific features."""
    if platform_manager.is_orangepi() and platform_manager.supports_feature("screenshot"):
        # Ensure screenshot directory exists
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Screenshot directory created: {settings.screenshot_dir}")


async def _validate_core_services(container):
    """Validate that core services are working."""
    try:
        # Test health service
        health_service = container.get(HealthServiceInterface)
        is_healthy = await health_service.is_healthy()
        logger.info(f"Health service validation: {'✓' if is_healthy else '✗'}")
        
        # Test metrics facade
        metrics_facade = container.get(MetricsFacade)
        health_status = await metrics_facade.is_system_healthy()
        logger.info(f"Metrics facade validation: {'✓' if health_status else '✗'}")
        
    except Exception as e:
        logger.warning(f"Service validation warning: {str(e)}")


# Initialize FastAPI app with improved configuration
app = FastAPI(
    title="OrangeAd Unified Device API",
    description="Platform-agnostic device monitoring and management API with dependency injection architecture",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.dev.enable_docs else None,
    redoc_url="/redoc" if settings.dev.enable_docs else None,
)

# Add middleware in correct order
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestTrackingMiddleware)
app.add_middleware(TailscaleSubnetMiddleware, allowed_subnet=settings.network.tailscale_subnet)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Improved routes with dependency injection
@app.get("/")
@inject_services
async def root():
    """Root endpoint with service information."""
    return {
        "service": "OrangeAd Unified Device API",
        "version": APP_VERSION,
        "platform": platform_manager.platform,
        "architecture": "dependency_injection",
        "status": "operational"
    }


@app.get("/platform")
@inject_services
async def platform_info():
    """Platform information endpoint."""
    return {
        "platform": platform_manager.platform,
        "service_manager": platform_manager.get_service_manager(),
        "bin_paths": [str(p) for p in platform_manager.config["bin_paths"]],
        "temp_dir": str(platform_manager.config["temp_dir"]),
        "features": platform_manager.get_available_features(),
        "config": platform_manager.config
    }


@app.get("/health")
@inject_services
async def health_check(health_service: HealthServiceInterface):
    """Health check endpoint using dependency injection."""
    try:
        is_healthy = await health_service.is_healthy()
        health_metrics = await health_service.get_health_metrics()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": health_metrics.timestamp.isoformat(),
            "metrics": health_metrics.dict(),
            "service": "operational"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "service": "degraded"
        }


@app.get("/health/detailed")
@inject_services
async def detailed_health_report(health_service: HealthServiceInterface):
    """Detailed health report endpoint."""
    try:
        report = await health_service.get_detailed_health_report()
        return report
    except Exception as e:
        logger.error(f"Detailed health report failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "service": "degraded"
        }


@app.get("/metrics")
@inject_services
async def system_metrics(metrics_facade: MetricsFacade):
    """System metrics endpoint using dependency injection."""
    try:
        metrics = await metrics_facade.get_system_metrics()
        return {
            "metrics": metrics,
            "timestamp": "utc_now",
            "source": "unified_metrics_collector"
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {str(e)}")
        return {
            "error": str(e),
            "metrics": {},
            "status": "collection_failed"
        }


@app.get("/system/info")
@inject_services
async def system_info(health_service: HealthServiceInterface):
    """System information endpoint."""
    try:
        info = await health_service.get_system_info()
        return info.dict()
    except Exception as e:
        logger.error(f"System info collection failed: {str(e)}")
        return {
            "error": str(e),
            "status": "collection_failed"
        }


@app.get("/services/status")
@inject_services
async def services_status():
    """Service registry status endpoint."""
    try:
        bootstrap_info = get_bootstrap_info()
        return {
            "dependency_injection": {
                "initialized": bootstrap_info['initialized'],
                "registered_services": bootstrap_info['registered_services'],
                "service_count": bootstrap_info['service_count'],
                "platform": bootstrap_info['platform']
            },
            "status": "operational"
        }
    except Exception as e:
        logger.error(f"Service status check failed: {str(e)}")
        return {
            "error": str(e),
            "status": "error"
        }


# Platform-specific route inclusion
if platform_manager.is_macos():
    logger.info("Loading macOS-specific routers")
    try:
        from src.oaDeviceAPI.platforms.macos.routers.health import router as macos_health_router
        from src.oaDeviceAPI.platforms.macos.routers.services import router as macos_services_router
        from src.oaDeviceAPI.platforms.macos.routers.camera import router as macos_camera_router
        
        app.include_router(macos_health_router, prefix="/macos", tags=["macOS"])
        app.include_router(macos_services_router, prefix="/services", tags=["Services"])
        app.include_router(macos_camera_router, prefix="/camera", tags=["Camera"])
        
        logger.info("macOS routers loaded successfully")
    except ImportError as e:
        logger.warning(f"Failed to load macOS routers: {str(e)}")

elif platform_manager.is_orangepi() or platform_manager.is_linux():
    logger.info("Loading OrangePi/Linux-specific routers")
    try:
        from src.oaDeviceAPI.platforms.orangepi.routers.health import router as orangepi_health_router
        from src.oaDeviceAPI.platforms.orangepi.routers.screenshot import router as orangepi_screenshot_router
        
        app.include_router(orangepi_health_router, prefix="/orangepi", tags=["OrangePi"])
        app.include_router(orangepi_screenshot_router, prefix="/screenshot", tags=["Screenshot"])
        
        logger.info("OrangePi/Linux routers loaded successfully")
    except ImportError as e:
        logger.warning(f"Failed to load OrangePi routers: {str(e)}")


if __name__ == "__main__":
    logger.info("Starting oaDeviceAPI server with improved architecture...")
    uvicorn.run(
        "main_improved:app",
        host=settings.network.host,
        port=settings.network.port,
        reload=settings.dev.enable_reload,
        log_level=settings.log_level.lower()
    )