"""
Camera Router Module

This module provides API endpoints for camera detection and streaming.
Implements MJPEG streaming for camera feeds.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from ....models.schemas import CameraInfo, CameraListResponse, ErrorResponse
from ..services.camera import (
    check_camera_availability,
    generate_mjpeg_frames,
    get_camera_by_id,
    get_camera_list,
    release_camera_capture,
)

router = APIRouter()


@router.get("/cameras", response_model=CameraListResponse)
async def list_cameras():
    """
    Get a list of all available cameras on the system.

    Returns:
        List of camera information objects or empty list if no cameras found
    """
    cameras = get_camera_list()

    return {
        "cameras": cameras,
        "count": len(cameras),
        "device_has_camera_support": len(cameras) > 0,
    }


@router.get("/cameras/status")
async def camera_status():
    """
    Check the status of camera availability on the system.

    Returns:
        Status information about camera availability
    """
    return check_camera_availability()


@router.get("/cameras/{camera_id}")
async def get_camera(camera_id: str):
    """
    Get information about a specific camera.

    Args:
        camera_id: The ID of the camera to retrieve

    Returns:
        Camera information if found
    """
    camera = get_camera_by_id(camera_id)

    if not camera:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "error",
                "message": f"Camera with ID {camera_id} not found",
            },
        )

    return camera


@router.get("/cameras/{camera_id}/stream")
async def stream_camera(camera_id: str, background_tasks: BackgroundTasks):
    """
    Stream video from a specific camera.

    This endpoint returns an MJPEG stream from the specified camera.

    Args:
        camera_id: The ID of the camera to stream from
        background_tasks: FastAPI background tasks for cleanup

    Returns:
        MJPEG stream response
    """
    # First check if the camera exists
    camera = get_camera_by_id(camera_id)

    if not camera:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "error",
                "message": f"Camera with ID {camera_id} not found",
            },
        )

    try:
        # Create a generator for MJPEG frames
        mjpeg_generator = generate_mjpeg_frames(camera_id)

        # Add a background task to release the camera when the stream ends
        # This ensures resources are cleaned up properly
        background_tasks.add_task(release_camera_capture, camera_id)

        # Return a streaming response with the MJPEG content type
        return StreamingResponse(
            mjpeg_generator,
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logging.exception(f"Error streaming from camera {camera_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": f"Failed to stream from camera: {str(e)}",
                "camera": camera.dict(),
            },
        )
