"""OrangePi camera service implementation."""

from typing import Any


class OrangePiCameraService:
    """OrangePi camera service (not available)."""

    async def get_camera_info(self) -> dict[str, Any]:
        """Get camera info - not available."""
        return {'available': False, 'platform': 'orangepi'}

    async def capture_image(self) -> bytes | None:
        """Capture image - not available."""
        return None

    def is_available(self) -> bool:
        """Camera not available on OrangePi."""
        return False
