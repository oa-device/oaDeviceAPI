"""macOS camera service implementation."""

from typing import Any


class MacOSCameraService:
    """macOS camera service."""

    async def get_camera_info(self) -> dict[str, Any]:
        """Get camera information."""
        return {'available': True, 'platform': 'macos'}

    async def capture_image(self) -> bytes | None:
        """Capture image from camera."""
        return None  # Placeholder

    def is_available(self) -> bool:
        """Check if camera is available."""
        return True
