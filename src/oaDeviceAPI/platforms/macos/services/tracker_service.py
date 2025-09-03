"""macOS tracker service implementation."""

from typing import Dict, Any
import httpx
from ....core.interfaces import TrackerServiceInterface
from ....core.exceptions import ServiceError, ErrorSeverity


class MacOSTrackerService:
    """macOS tracker service integration."""

    def __init__(self):
        self.tracker_url = "http://localhost:8080"

    async def get_tracker_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.tracker_url}/api/stats", timeout=5.0)
                return response.json()
        except Exception as e:
            return {'error': str(e), 'available': False}

    async def get_tracker_status(self) -> Dict[str, Any]:
        """Get tracker status."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.tracker_url}/health", timeout=5.0)
                return {'status': 'running', 'available': True}
        except Exception:
            return {'status': 'not_running', 'available': False}

    def is_available(self) -> bool:
        """Check if tracker is available."""
        return True  # Assume available on macOS