"""OrangePi screenshot service implementation."""

from typing import Optional


class OrangePiScreenshotService:
    """OrangePi screenshot service."""

    async def capture_screenshot(self) -> Optional[bytes]:
        """Capture screenshot."""
        return b"placeholder_screenshot_data"  # Placeholder

    def is_supported(self) -> bool:
        """Screenshots supported on OrangePi."""
        return True