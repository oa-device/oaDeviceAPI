"""Unified models for oaDeviceAPI."""

# Import from shared schemas to maintain compatibility
from .health_schemas import (
    BaseCPUMetrics,
    BaseMemoryMetrics, 
    BaseDiskMetrics,
    BaseNetworkMetrics,
    BaseHealthMetrics,
    BaseSystemInfo,
    BaseDeviceInfo,
    BaseVersionInfo,
    BaseCapabilities,
    MacOSCapabilities,
    OrangePiCapabilities,
    BaseHealthResponse,
    MacOSHealthResponse,
    OrangePiHealthResponse,
    StandardizedErrorResponse,
)

__all__ = [
    "BaseCPUMetrics",
    "BaseMemoryMetrics",
    "BaseDiskMetrics", 
    "BaseNetworkMetrics",
    "BaseHealthMetrics",
    "BaseSystemInfo",
    "BaseDeviceInfo",
    "BaseVersionInfo",
    "BaseCapabilities",
    "MacOSCapabilities",
    "OrangePiCapabilities",
    "BaseHealthResponse",
    "MacOSHealthResponse",
    "OrangePiHealthResponse",
    "StandardizedErrorResponse",
]