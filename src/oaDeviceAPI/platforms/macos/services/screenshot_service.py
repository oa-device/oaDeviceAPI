"""macOS screenshot service implementation."""




class MacOSScreenshotService:
    """macOS screenshot service (not supported)."""

    async def capture_screenshot(self) -> bytes | None:
        """Capture screenshot - not supported on macOS."""
        return None

    def is_supported(self) -> bool:
        """Screenshots not supported on macOS."""
        return False
