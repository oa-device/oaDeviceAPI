import platform
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ....core.config import APP_VERSION, settings
from ....models.health_schemas import StandardizedErrorResponse, MacOSHealthResponse
from ..services.display import get_display_info
from ..services.health import get_health_summary
from ..services.system import get_device_info, get_system_metrics, get_version_info
from ..services.standardized_metrics import (
    get_standardized_health_metrics,
    get_standardized_system_info,
    get_standardized_device_info,
    get_standardized_version_info,
    get_standardized_capabilities
)
from ..services.temperature import get_temperature_metrics
from ..services.tracker import check_tracker_status, get_deployment_info
from ..services.utils import cache_with_ttl

router = APIRouter()


# Cache expensive operations
@cache_with_ttl(CACHE_TTL)
def get_cached_metrics() -> Dict:
    return get_system_metrics()


@cache_with_ttl(CACHE_TTL)
def get_cached_display_info() -> Dict:
    return get_display_info()


@cache_with_ttl(CACHE_TTL)
def get_cached_deployment_info() -> Dict:
    return get_deployment_info()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Get comprehensive system health status and raw metrics using standardized schemas."""
    try:
        # Get standardized metrics
        standardized_metrics = get_standardized_health_metrics()
        standardized_system = get_standardized_system_info()
        standardized_device = get_standardized_device_info()
        standardized_version = get_standardized_version_info()
        standardized_capabilities = get_standardized_capabilities()
        
        # Use cached versions of expensive operations for additional data
        deployment = get_cached_deployment_info()
        display_info = get_cached_display_info()
        tracker = check_tracker_status()  # Don't cache this as it needs to be real-time
        device = get_device_info()

        # Get current time in UTC
        now = datetime.now(timezone.utc)

        # Determine basic status from tracker health (for backward compatibility)
        status = "online"
        if not tracker["healthy"]:
            status = (
                "maintenance" if tracker["service_status"] == "active" else "offline"
            )

        # Format response using standardized schemas while maintaining backward compatibility
        return {
            "status": status,
            "hostname": standardized_device.hostname,
            "timestamp": now.isoformat(),
            "timestamp_epoch": int(now.timestamp()),
            "version": standardized_version.dict(),
            "metrics": standardized_metrics.dict(),
            "deployment": deployment,
            "tracker": tracker,  # Using tracker instead of player for Mac devices
            "device_info": standardized_device.dict(),  # Standardized device info
            "system": standardized_system.dict(),  # Standardized system information
            "display": {
                "connected_displays": len(display_info.get("displays", [])),
                "main_display": display_info.get("main_display", {}),
                "all_displays": display_info.get("displays", []),
                "is_headless": device.get("is_headless", False),
                "headless_reason": (
                    display_info.get("headless_reason", None)
                    if device.get("is_headless", False)
                    else None
                ),
            },
            "capabilities": standardized_capabilities.dict(),
            "_cache_info": {
                "metrics": get_cached_metrics.cache_info(),
                "display": get_cached_display_info.cache_info(),
                "deployment": get_cached_deployment_info.cache_info(),
            },
        }
    except Exception as e:
        now = datetime.now(timezone.utc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                timestamp=now.isoformat(),
                timestamp_epoch=int(now.timestamp()),
                error=str(e),
            ).dict(),
        )


@router.get("/health/summary")
async def health_summary():
    """Get a summary of system health with recommendations."""
    try:
        metrics = get_cached_metrics()
        tracker = check_tracker_status()
        display_info = get_cached_display_info()

        return get_health_summary(metrics, tracker, display_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temperature")
async def temperature_metrics():
    """Get detailed temperature metrics for the macOS device."""
    try:
        temperature_data = get_temperature_metrics()
        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": temperature_data
        }
    except Exception as e:
        now = datetime.now(timezone.utc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                timestamp=now.isoformat(),
                timestamp_epoch=int(now.timestamp()),
                error=str(e),
            ).dict(),
        )
