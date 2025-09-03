"""macOS screenshot service implementation."""

from typing import Optional
from ....core.interfaces import ScreenshotServiceInterface


class MacOSScreenshotService:
    """macOS screenshot service (not supported)."""

    async def capture_screenshot(self) -> Optional[bytes]:
        """Capture screenshot - not supported on macOS."""
        return None

    def is_supported(self) -> bool:
        """Screenshots not supported on macOS."""
        return False