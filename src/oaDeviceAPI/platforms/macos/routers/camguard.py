import logging

from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

# CamGuard service configuration
CAMGUARD_SERVICE_NAME = "com.orangead.camguard"
CAMGUARD_CLEANUP_SERVICE_NAME = "com.orangead.camguard.cleanup"


@router.get("/camguard/status")
async def get_camguard_status():
    """Get comprehensive CamGuard status - recording and streaming"""
    try:
        from ..services.camguard import (
            get_camguard_service_status,
            get_recording_status,
            get_stream_url,
        )

        # Get recording service status
        recording_service_status = get_camguard_service_status()

        # Get recording status
        recording_status = get_recording_status()

        # Get streaming status
        streaming_status = get_stream_url()

        # Determine overall health
        recording_healthy = (
            recording_service_status.get("running", False) and
            recording_status.get("recording_active", False) and
            not recording_status.get("disk_full", True)
        )

        streaming_healthy = (
            streaming_status.get("enabled", False) and
            streaming_status.get("server_status") == "online"
        )

        # Overall status considers both recording and streaming
        overall_status = "online" if recording_healthy else "error"
        if streaming_status.get("enabled", False) and not streaming_healthy:
            overall_status = "warning"  # Recording works but streaming has issues

        return {
            "recording_service": recording_service_status,
            "recording_status": recording_status,
            "streaming_status": {
                "enabled": streaming_status.get("enabled", False),
                "stream_url": streaming_status.get("rtsp_url"),
                "server_status": streaming_status.get("server_status", "unknown"),
                "stream_active": streaming_status.get("active", False),
                "mediamtx_running": streaming_status.get("mediamtx_running", False)
            },
            "recording_healthy": recording_healthy,
            "streaming_healthy": streaming_healthy,
            "status": overall_status,
            "timestamp": recording_status.get("timestamp")
        }

    except Exception as e:
        logger.error(f"Error getting CamGuard status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting CamGuard status: {str(e)}"
        )


@router.get("/camguard/recordings")
async def get_camguard_recordings(limit: int = 50):
    """List recent CamGuard recordings"""
    try:
        from ..services.camguard import get_recordings_list

        recordings = get_recordings_list(limit=limit)

        return {
            "recordings": recordings,
            "count": len(recordings),
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Error getting CamGuard recordings: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting recordings: {str(e)}"
        )


@router.get("/camguard/storage")
async def get_camguard_storage_info():
    """Get CamGuard storage usage and configuration"""
    try:
        from ..services.camguard import get_storage_info

        storage_info = get_storage_info()

        return storage_info

    except Exception as e:
        logger.error(f"Error getting CamGuard storage info: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting storage info: {str(e)}"
        )


@router.post("/camguard/actions/restart")
async def restart_camguard_service():
    """Restart the CamGuard recording service"""
    try:
        from ..services.camguard import restart_camguard_service

        result = restart_camguard_service()

        if result.get("success", False):
            return {"message": "CamGuard service restart initiated", "details": result}
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restart CamGuard service: {result.get('error', 'Unknown error')}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting CamGuard service: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error restarting service: {str(e)}"
        )


@router.post("/camguard/actions/cleanup")
async def trigger_camguard_cleanup():
    """Manually trigger CamGuard storage cleanup"""
    try:
        from ..services.camguard import trigger_cleanup

        result = trigger_cleanup()

        if result.get("success", False):
            return {"message": "CamGuard cleanup initiated", "details": result}
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to trigger cleanup: {result.get('error', 'Unknown error')}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering CamGuard cleanup: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error triggering cleanup: {str(e)}"
        )


@router.get("/camguard/stream_url")
async def get_camguard_stream_url():
    """Get the RTSP stream URL for live camera feed"""
    try:
        from ..services.camguard import get_stream_url

        stream_info = get_stream_url()

        return {
            "stream_url": stream_info.get("rtsp_url"),
            "streaming_enabled": stream_info.get("enabled", False),
            "stream_active": stream_info.get("active", False),
            "server_status": stream_info.get("server_status", "unknown")
        }

    except Exception as e:
        logger.error(f"Error getting CamGuard stream URL: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting stream URL: {str(e)}"
        )


