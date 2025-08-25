"""
macOS Camera Services Module

This module provides functions to detect and stream from macOS cameras.
It uses system_profiler to detect cameras and opencv for streaming.

Implements MJPEG streaming functionality for camera feeds.
"""

import hashlib
import json
import logging
import re
import shlex
import subprocess
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Generator, Iterator, List, Optional

import cv2
import numpy as np
from fastapi import HTTPException

from ..models.schemas import CameraInfo

# Configure logger
logger = logging.getLogger(__name__)


def get_camera_list() -> List[CameraInfo]:
    """
    Get a list of all available cameras on the macOS system.

    Uses system_profiler to detect cameras and their properties.

    Returns:
        List[CameraInfo]: List of camera information objects
    """
    try:
        # Run system_profiler to get camera information
        cmd = ["system_profiler", "SPCameraDataType", "-json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse the JSON output
        camera_data = json.loads(result.stdout)

        # Extract camera information
        cameras = []

        # Check if Camera section exists
        if "SPCameraDataType" in camera_data and camera_data["SPCameraDataType"]:
            for camera_entry in camera_data["SPCameraDataType"]:
                # Each camera might have different property names
                # Extract common properties
                camera_name = camera_entry.get("_name", "Unknown Camera")

                # Generate a deterministic ID for the camera based on its properties
                # This ensures the same camera gets the same ID across API restarts
                id_string = f"{camera_name}_{camera_entry.get('model_id', '')}_{camera_entry.get('manufacturer', '')}"
                camera_id = hashlib.md5(id_string.encode()).hexdigest()[:8]

                # Check if it's a built-in camera
                is_built_in = "FaceTime" in camera_name or "Built-in" in camera_name

                # Create camera info object
                camera_info = CameraInfo(
                    id=camera_id,
                    name=camera_name,
                    model=camera_entry.get("model_id", None),
                    manufacturer=camera_entry.get("manufacturer", None),
                    is_built_in=is_built_in,
                    is_connected=True,  # Assume connected if detected
                    location="Built-in" if is_built_in else "External",
                )

                cameras.append(camera_info)

        return cameras

    except subprocess.SubprocessError as e:
        logger.error(f"Error running system_profiler: {str(e)}")
        return []

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing system_profiler output: {str(e)}")
        return []

    except Exception as e:
        logger.error(f"Unexpected error detecting cameras: {str(e)}")
        return []


def get_camera_by_id(camera_id: str) -> Optional[CameraInfo]:
    """
    Get a specific camera by its ID.

    Args:
        camera_id: The ID of the camera to retrieve

    Returns:
        CameraInfo: Camera information if found, None otherwise
    """
    cameras = get_camera_list()

    for camera in cameras:
        if camera.id == camera_id:
            return camera

    return None


def check_camera_availability() -> Dict:
    """
    Check if the Tracker's camera feed is available.

    Returns:
        Dict: Status information about camera availability
    """
    # First get the regular camera list
    cameras = get_camera_list()

    # Then check if the Tracker's camera feed is accessible
    tracker_available = False
    try:
        import requests

        # Just check if the endpoint is responding, don't download the full image
        response = requests.head("http://localhost:8080/cam.jpg", timeout=1)
        tracker_available = response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to check Tracker camera feed: {str(e)}")

    return {
        "status": "ok" if (cameras and tracker_available) else "no_cameras",
        "camera_count": len(cameras),
        "cameras": [cam.dict() for cam in cameras],
        "tracker_available": tracker_available,
        "timestamp": datetime.now().isoformat(),
    }


# Dictionary to keep track of active camera captures
# This prevents opening multiple captures for the same camera
_active_captures = {}
_captures_lock = threading.Lock()


def _get_camera_index(camera_id: str) -> int:
    """
    Get the camera index for OpenCV based on the camera ID.

    This is a simple implementation that maps our camera IDs to OpenCV indices.
    In a real implementation, you might need a more sophisticated mapping.

    Args:
        camera_id: The ID of the camera

    Returns:
        int: The OpenCV camera index (usually 0 for built-in camera)
    """
    # Get all cameras
    cameras = get_camera_list()

    # Find the camera with the matching ID
    matching_cameras = [i for i, cam in enumerate(cameras) if cam.id == camera_id]

    if not matching_cameras:
        raise HTTPException(
            status_code=404, detail=f"Camera with ID {camera_id} not found"
        )

    # Return the first matching camera's index
    # This is a simplification - in reality, the mapping between our camera IDs
    # and OpenCV indices might be more complex
    return matching_cameras[0]


def get_camera_capture(camera_id: str) -> cv2.VideoCapture:
    """
    Get a VideoCapture object for the specified camera.

    Instead of trying to access the camera directly, this function now proxies
    the Tracker's camera feed to avoid conflicts with the Tracker's exclusive
    camera access.

    Args:
        camera_id: The ID of the camera

    Returns:
        cv2.VideoCapture: The camera capture object

    Raises:
        HTTPException: If the camera feed cannot be accessed
    """
    global _active_captures

    with _captures_lock:
        # Check if we already have an active capture for this camera
        if camera_id in _active_captures:
            capture = _active_captures[camera_id]

            # Check if the capture is still open
            if capture.isOpened():
                return capture
            else:
                # Remove the closed capture
                del _active_captures[camera_id]

        # Instead of accessing the camera directly, use the Tracker's camera feed
        # The Tracker serves its camera feed at http://localhost:8080/cam.jpg
        tracker_feed_url = "http://localhost:8080/cam.jpg"

        # Create a new capture using the Tracker's feed URL
        capture = cv2.VideoCapture(tracker_feed_url)

        if not capture.isOpened():
            logger.error(f"Failed to access Tracker camera feed at {tracker_feed_url}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to access camera feed for camera ID {camera_id}. The Tracker may not be running.",
            )

        # Store the capture
        _active_captures[camera_id] = capture

        return capture


def release_camera_capture(camera_id: str) -> None:
    """
    Release a camera capture.

    Args:
        camera_id: The ID of the camera to release
    """
    global _active_captures

    with _captures_lock:
        if camera_id in _active_captures:
            _active_captures[camera_id].release()
            del _active_captures[camera_id]


def generate_mjpeg_frames(camera_id: str) -> Generator[bytes, None, None]:
    """
    Generate MJPEG frames from the camera.

    This function yields JPEG-encoded frames in the format required for
    MJPEG streaming over HTTP. It now uses the Tracker's camera feed
    to avoid conflicts with the Tracker's exclusive camera access.

    Args:
        camera_id: The ID of the camera to stream from

    Yields:
        bytes: JPEG-encoded frame with MJPEG multipart headers
    """
    try:
        # Get the camera capture (now proxying from Tracker)
        capture = get_camera_capture(camera_id)

        while True:
            # Read a frame from the Tracker's feed
            success, frame = capture.read()

            if not success:
                logger.error(f"Failed to read frame from camera {camera_id}")
                break

            # Encode the frame as JPEG
            _, jpeg_frame = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

            # Convert to bytes
            frame_bytes = jpeg_frame.tobytes()

            # Yield the frame with MJPEG multipart headers
            yield b"--frame\r\n"
            yield b"Content-Type: image/jpeg\r\n\r\n"
            yield frame_bytes
            yield b"\r\n"

            # Control the frame rate
            time.sleep(1 / 15)  # Aim for 15 FPS

    except Exception as e:
        logger.exception(f"Error streaming from camera {camera_id}: {str(e)}")

    finally:
        # Don't release the capture here, as it might be used by other streams
        # We'll rely on the capture pool management to handle this
        pass
