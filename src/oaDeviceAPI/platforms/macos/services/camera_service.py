"""macOS camera service implementation."""

from typing import Dict, Any, Optional
from ....core.interfaces import CameraServiceInterface


class MacOSCameraService:
    """macOS camera service."""

    async def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information."""
        return {'available': True, 'platform': 'macos'}

    async def capture_image(self) -> Optional[bytes]:
        """Capture image from camera."""
        return None  # Placeholder

    def is_available(self) -> bool:
        """Check if camera is available."""
        return True