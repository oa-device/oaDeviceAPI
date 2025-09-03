"""OrangePi camera service implementation."""

from typing import Dict, Any, Optional


class OrangePiCameraService:
    """OrangePi camera service (not available)."""

    async def get_camera_info(self) -> Dict[str, Any]:
        """Get camera info - not available."""
        return {'available': False, 'platform': 'orangepi'}

    async def capture_image(self) -> Optional[bytes]:
        """Capture image - not available."""
        return None

    def is_available(self) -> bool:
        """Camera not available on OrangePi."""
        return False