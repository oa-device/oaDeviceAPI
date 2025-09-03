"""OrangePi tracker service implementation."""

from typing import Dict, Any


class OrangePiTrackerService:
    """OrangePi tracker service (not available)."""

    async def get_tracker_stats(self) -> Dict[str, Any]:
        """Get tracker stats - not available on OrangePi."""
        return {'available': False, 'platform': 'orangepi'}

    async def get_tracker_status(self) -> Dict[str, Any]:
        """Get tracker status."""
        return {'status': 'not_available', 'available': False}

    def is_available(self) -> bool:
        """Tracker not available on OrangePi."""
        return False