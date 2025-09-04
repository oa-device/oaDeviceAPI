"""
Additional schemas for unified device API
"""

from pydantic import BaseModel, ConfigDict


class CameraInfo(BaseModel):
    """Camera information schema."""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    model: str | None = None
    manufacturer: str | None = None
    is_built_in: bool = False
    is_connected: bool = True
    is_available: bool = True  # Added to match oaDashboard schema
    resolution: dict[str, int] | None = None  # Changed to match oaDashboard schema
    location: str | None = None  # e.g., "Built-in", "USB", etc.


class CameraListResponse(BaseModel):
    """Camera list response schema."""
    model_config = ConfigDict(extra="allow")

    cameras: list[CameraInfo]
    count: int
    device_has_camera_support: bool = True  # Changed to match oaDashboard schema


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    model_config = ConfigDict(extra="allow")

    status: str = "error"
    timestamp: str
    timestamp_epoch: int
    error: str
