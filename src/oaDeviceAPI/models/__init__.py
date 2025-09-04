"""Unified models for oaDeviceAPI."""

# Import from shared schemas to maintain compatibility
from .health_schemas import (
    BaseCapabilities,
    BaseCPUMetrics,
    BaseDeviceInfo,
    BaseDiskMetrics,
    BaseHealthMetrics,
    BaseHealthResponse,
    BaseMemoryMetrics,
    BaseNetworkMetrics,
    BaseSystemInfo,
    BaseVersionInfo,
    MacOSCapabilities,
    MacOSHealthResponse,
    OrangePiCapabilities,
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
