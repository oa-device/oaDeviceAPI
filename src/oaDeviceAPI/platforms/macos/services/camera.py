"""
macOS Camera Services Module

This module provides functions to detect and stream from macOS cameras.
It uses system_profiler to detect cameras and opencv for streaming.

Implements MJPEG streaming functionality for camera feeds.
"""

import hashlib
import json
import logging
import subprocess
import threading
import time
from collections.abc import Generator
from datetime import datetime

# Graceful handling of optional dependencies
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None
    np = None

from fastapi import HTTPException

from ....models.schemas import CameraInfo

# Configure logger
logger = logging.getLogger(__name__)


def get_camera_list() -> list[CameraInfo]:
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


def get_camera_by_id(camera_id: str) -> CameraInfo | None:
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


def check_camera_availability() -> dict:
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


def get_camera_capture(camera_id: str):
    """
    Get a VideoCapture object for the specified camera.

    Args:
        camera_id: The ID of the camera to capture from

    Returns:
        cv2.VideoCapture or None: Video capture object, or None if cv2 not available
    """
    if not CV2_AVAILABLE:
        logger.error("OpenCV (cv2) not available - cannot create camera capture")
        return None

    try:
        # Convert camera_id to integer if it's numeric
        if camera_id.isdigit():
            capture_index = int(camera_id)
        else:
            # For non-numeric IDs, try to find the camera and use index 0 as fallback
            cameras = get_camera_list()
            capture_index = 0  # Default to first camera

            for i, camera in enumerate(cameras):
                if camera.id == camera_id:
                    capture_index = i
                    break

        capture = cv2.VideoCapture(capture_index)

        if not capture.isOpened():
            logger.error(f"Failed to open camera {camera_id} at index {capture_index}")
            return None

        # Set some basic properties
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)

        return capture

    except Exception as e:
        logger.error(f"Error creating camera capture for {camera_id}: {str(e)}")
        return None


def generate_mjpeg_stream(capture) -> Generator[bytes, None, None]:
    """
    Generate MJPEG stream from camera capture.

    Args:
        capture: cv2.VideoCapture object

    Yields:
        bytes: MJPEG frame data
    """
    if not CV2_AVAILABLE or capture is None:
        logger.error("OpenCV not available or invalid capture - cannot generate stream")
        return

    try:
        while True:
            ret, frame = capture.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                break

            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            # Yield frame in MJPEG format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            # Small delay to prevent overwhelming the client
            time.sleep(0.033)  # ~30 FPS

    except Exception as e:
        logger.error(f"Error in MJPEG stream generation: {str(e)}")

    finally:
        if capture:
            capture.release()


def generate_mjpeg_frames(camera_id: str) -> Generator[bytes, None, None]:
    """
    Generate MJPEG frames for a specific camera ID.

    This is the main function expected by the router that handles
    the complete workflow from camera_id to MJPEG stream.

    Args:
        camera_id: The ID of the camera to stream from

    Yields:
        bytes: MJPEG frame data
    """
    if not CV2_AVAILABLE:
        logger.error("OpenCV (cv2) not available - cannot generate MJPEG frames")
        return

    capture = get_camera_capture(camera_id)
    if capture is None:
        logger.error(f"Failed to get camera capture for camera {camera_id}")
        return

    # Use the existing stream generator
    yield from generate_mjpeg_stream(capture)


def release_camera_capture(camera_id: str) -> None:
    """
    Release camera capture resources for a specific camera.

    This function is called by the router as a background task
    to ensure proper cleanup of camera resources.

    Args:
        camera_id: The ID of the camera to release
    """
    with _captures_lock:
        if camera_id in _active_captures:
            try:
                capture = _active_captures[camera_id]
                if capture and capture.isOpened():
                    capture.release()
                    logger.info(f"Released camera capture for camera {camera_id}")
            except Exception as e:
                logger.error(f"Error releasing camera capture for {camera_id}: {str(e)}")
            finally:
                del _active_captures[camera_id]
        else:
            logger.debug(f"No active capture found for camera {camera_id}")
