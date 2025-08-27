"""
Additional schemas for unified device API
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field


class CameraInfo(BaseModel):
    id: str
    name: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    is_built_in: bool = False
    is_connected: bool = True
    is_available: bool = True  # Added to match oaDashboard schema
    resolution: Optional[Dict[str, int]] = None  # Changed to match oaDashboard schema
    location: Optional[str] = None  # e.g., "Built-in", "USB", etc.

    class Config:
        extra = "allow"


class CameraListResponse(BaseModel):
    cameras: List[CameraInfo]
    count: int
    device_has_camera_support: bool = True  # Changed to match oaDashboard schema

    class Config:
        extra = "allow"


class ErrorResponse(BaseModel):
    status: str = "error"
    timestamp: str
    timestamp_epoch: int
    error: str