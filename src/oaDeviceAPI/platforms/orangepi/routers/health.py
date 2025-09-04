import platform
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ....core.config import settings
from ....core.utils import cache_with_ttl
from ....models.health_schemas import OrangePiHealthResponse, StandardizedErrorResponse
from ..services.display import get_display_info
from ..services.health import get_health_summary
from ..services.player import check_player_status, get_deployment_info
from ..services.standardized_metrics import (
    get_standardized_capabilities,
    get_standardized_device_info,
    get_standardized_health_metrics,
    get_standardized_system_info,
    get_standardized_version_info,
)
from ..services.system import get_device_info, get_system_metrics

# Constants
CACHE_TTL = getattr(settings, 'cache_ttl', 30)

router = APIRouter()


# Cache expensive operations
@cache_with_ttl(CACHE_TTL)
def get_cached_metrics() -> dict:
    return get_system_metrics()


@cache_with_ttl(CACHE_TTL)
def get_cached_display_info() -> dict:
    return get_display_info()


@cache_with_ttl(CACHE_TTL)
def get_cached_deployment_info() -> dict:
    return get_deployment_info()


@router.get("/health", response_model=OrangePiHealthResponse)
async def health_check():
    """Get comprehensive system health status and raw metrics using standardized schemas."""
    try:
        # Get standardized metrics
        standardized_metrics = get_standardized_health_metrics()
        get_standardized_system_info()
        standardized_device = get_standardized_device_info()
        standardized_version = get_standardized_version_info()
        standardized_capabilities = get_standardized_capabilities()

        # Use cached versions of expensive operations for additional data
        deployment = get_cached_deployment_info()
        display_info = get_cached_display_info()
        player = check_player_status()  # Don't cache this as it needs to be real-time
        get_device_info()

        # Get current time in UTC
        now = datetime.now(UTC)

        # Determine basic status from player health (for backward compatibility)
        status = "online"
        if not player["healthy"]:
            status = "maintenance" if player["service_status"] == "active" else "offline"

        # Format response using standardized schemas while maintaining backward compatibility
        # Use safe attribute access for hostname to handle both Pydantic and non-Pydantic cases
        device_hostname = getattr(standardized_device, 'hostname', None) or platform.node()

        return {
            "status": status,
            "hostname": device_hostname,
            "timestamp": now.isoformat(),
            "timestamp_epoch": int(now.timestamp()),
            "version": standardized_version.dict(),
            "metrics": standardized_metrics.dict(),
            "deployment": deployment,
            "player": player,
            "device_info": standardized_device.dict(),  # Standardized device info
            "display": display_info,  # Include display info separately
            "capabilities": standardized_capabilities.dict(),
            "_cache_info": {
                "metrics": get_cached_metrics.cache_info(),
                "display": get_cached_display_info.cache_info(),
                "deployment": get_cached_deployment_info.cache_info(),
            },
        }
    except Exception as e:
        now = datetime.now(UTC)
        return JSONResponse(
            status_code=500,
            content=StandardizedErrorResponse(status="error", timestamp=now.isoformat(), timestamp_epoch=int(now.timestamp()), error=str(e)).dict(),
        )


@router.get("/health/summary")
async def health_summary():
    """Get a summary of system health with recommendations."""
    try:
        metrics = get_cached_metrics()
        player = check_player_status()
        display_info = get_cached_display_info()

        return get_health_summary(metrics, player, display_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
