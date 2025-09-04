import logging

import httpx
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from ....core.config import TRACKER_API_URL

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tracker/stats")
async def get_tracker_stats():
    """Proxy endpoint to fetch oaTracker statistics"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TRACKER_API_URL}/api/stats", timeout=5.0)
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error connecting to oaTracker API: {str(e)}")
        raise HTTPException(
            status_code=502, detail=f"Error connecting to oaTracker API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error accessing oaTracker API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/tracker/status")
async def get_tracker_status():
    """Get comprehensive oaTracker status including service and API health"""
    try:
        # First check if the API is accessible
        api_status = {"api_accessible": False, "stats": None, "error": None}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{TRACKER_API_URL}/api/stats", timeout=3.0)
                if response.status_code == 200:
                    api_status["api_accessible"] = True
                    api_status["stats"] = response.json()
        except Exception as e:
            api_status["error"] = str(e)

        # Get service status from the tracker service
        from ..services.tracker import check_tracker_status

        service_status = check_tracker_status()

        # Combine the information
        return {
            "service": service_status,
            "api": api_status,
            "healthy": service_status.get("healthy", False)
            and api_status["api_accessible"],
            "status": (
                "online"
                if (
                    service_status.get("healthy", False)
                    and api_status["api_accessible"]
                )
                else "error"
            ),
        }
    except Exception as e:
        logger.error(f"Error getting tracker status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting tracker status: {str(e)}"
        )


@router.get("/tracker/stream")
async def get_tracker_stream():
    """Proxy endpoint to access the oaTracker camera stream"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TRACKER_API_URL}/cam.jpg", timeout=10.0)

            # Return the image with the correct content type
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/jpeg"),
                status_code=response.status_code,
            )
    except httpx.RequestError as e:
        logger.error(f"Error connecting to oaTracker stream: {str(e)}")
        raise HTTPException(
            status_code=502, detail=f"Error connecting to oaTracker stream: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error accessing oaTracker stream: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/tracker/mjpeg")
async def get_tracker_mjpeg_stream():
    """Proxy endpoint to access the oaTracker MJPEG stream"""
    try:
        # Create a streaming response that forwards the MJPEG stream
        async def stream_generator():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "GET", f"{TRACKER_API_URL}/mjpeg", timeout=None
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_generator(), media_type="multipart/x-mixed-replace; boundary=frame"
        )
    except Exception as e:
        logger.error(f"Error streaming from oaTracker: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error streaming from oaTracker: {str(e)}"
        )
