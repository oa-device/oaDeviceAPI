"""OrangePi screenshot service implementation."""



class OrangePiScreenshotService:
    """OrangePi screenshot service."""

    async def capture_screenshot(self) -> bytes | None:
        """Capture screenshot."""
        return b"placeholder_screenshot_data"  # Placeholder

    def is_supported(self) -> bool:
        """Screenshots supported on OrangePi."""
        return True
