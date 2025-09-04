"""Health-related Pydantic schemas for standardized response structures."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseCPUMetrics(BaseModel):
    """Standardized CPU metrics structure."""
    model_config = ConfigDict(extra="allow")

    usage_percent: float = Field(..., description="CPU usage percentage (0-100)")
    cores: int = Field(..., description="Number of CPU cores")
    architecture: str | None = Field(None, description="CPU architecture (e.g., arm64, x86_64)")
    model: str | None = Field(None, description="CPU model name")


class BaseMemoryMetrics(BaseModel):
    """Standardized memory metrics structure."""
    model_config = ConfigDict(extra="allow")

    usage_percent: float = Field(..., description="Memory usage percentage (0-100)")
    total: int = Field(..., description="Total memory in bytes")
    used: int = Field(..., description="Used memory in bytes")
    available: int = Field(..., description="Available memory in bytes")


class BaseDiskMetrics(BaseModel):
    """Standardized disk metrics structure."""
    model_config = ConfigDict(extra="allow")

    usage_percent: float = Field(..., description="Disk usage percentage (0-100)")
    total: int = Field(..., description="Total disk space in bytes")
    used: int = Field(..., description="Used disk space in bytes")
    free: int = Field(..., description="Free disk space in bytes")
    path: str | None = Field(None, description="Disk mount path")


class BaseNetworkMetrics(BaseModel):
    """Standardized network metrics structure."""
    model_config = ConfigDict(extra="allow")

    bytes_sent: int = Field(..., description="Total bytes sent")
    bytes_received: int = Field(..., description="Total bytes received")
    packets_sent: int = Field(..., description="Total packets sent")
    packets_received: int = Field(..., description="Total packets received")
    interface: str | None = Field(None, description="Network interface name")


class BaseHealthMetrics(BaseModel):
    """Standardized base health metrics structure."""
    model_config = ConfigDict(extra="allow")

    cpu: BaseCPUMetrics = Field(..., description="CPU metrics")
    memory: BaseMemoryMetrics = Field(..., description="Memory metrics")
    disk: BaseDiskMetrics = Field(..., description="Disk metrics")
    network: BaseNetworkMetrics | None = Field(None, description="Network metrics")
    timestamp: datetime | None = Field(None, description="Metrics collection timestamp")
    overall_health: str | None = Field(None, description="Overall health status")


class BaseSystemInfo(BaseModel):
    """Standardized system information structure."""
    model_config = ConfigDict(extra="allow")

    os_version: str = Field(..., description="Operating system version")
    kernel_version: str | None = Field(None, description="Kernel version")
    hostname: str = Field(..., description="System hostname")
    uptime: float | None = Field(None, description="System uptime in seconds")
    uptime_human: str | None = Field(None, description="Human-readable uptime")
    boot_time: float | None = Field(None, description="Boot timestamp (Unix)")
    architecture: str | None = Field(None, description="System architecture")
    platform: dict[str, Any] | None = Field(None, description="Platform information")


class BaseDeviceInfo(BaseModel):
    """Standardized device information structure."""
    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Device type (Mac, OrangePi, etc.)")
    series: str = Field(..., description="Device series (Mac Mini, OrangePi 5B, etc.)")
    hostname: str = Field(..., description="Device hostname")
    model: str = Field(..., description="Device model")
    manufacturer: str | None = Field(None, description="Device manufacturer")
    serial_number: str | None = Field(None, description="Device serial number")
    location: str | None = Field(None, description="Physical device location")
    tags: list[str] = Field(default_factory=list, description="Device tags")


class BaseVersionInfo(BaseModel):
    """Standardized version information structure."""
    model_config = ConfigDict(extra="allow")

    api: str = Field(..., description="API version")
    python: str = Field(..., description="Python version")
    tailscale: str | None = Field(None, description="Tailscale version")
    system: dict[str, Any] = Field(default_factory=dict, description="System information")


class BaseCapabilities(BaseModel):
    """Standardized capabilities structure."""
    model_config = ConfigDict(extra="allow")

    supports_reboot: bool = Field(..., description="Reboot capability")
    supports_ssh: bool = Field(default=True, description="SSH access capability")


class MacOSCapabilities(BaseCapabilities):
    """macOS specific capabilities."""
    supports_camera_stream: bool = Field(default=True, description="Camera stream support")
    supports_tracker_restart: bool = Field(default=True, description="Tracker restart support")
    supports_reboot: bool = Field(default=True, description="Reboot capability")
    supports_ssh: bool = Field(default=True, description="SSH access capability")
    device_has_camera_support: bool = Field(default=True, description="Camera hardware support")


class OrangePiCapabilities(BaseCapabilities):
    """OrangePi specific capabilities."""
    supports_screenshots: bool = Field(default=True, description="Screenshot capability")
    supports_player_restart: bool = Field(default=True, description="Player restart support")
    supports_display_setup: bool = Field(default=True, description="Display setup capability")
    supports_reboot: bool = Field(default=True, description="Reboot capability")
    supports_ssh: bool = Field(default=True, description="SSH access capability")
    device_has_camera_support: bool = Field(default=False, description="Camera hardware support")


# Base response for health endpoints (used by tests)
class BaseHealthResponse(BaseModel):
    """Base health response structure."""
    model_config = ConfigDict(extra="allow")

    status: str = Field(..., description="Overall status")
    hostname: str = Field(..., description="Device hostname")
    timestamp: str = Field(..., description="Response timestamp")
    timestamp_epoch: int = Field(..., description="Response timestamp epoch")
    version: BaseVersionInfo = Field(..., description="Version information")
    metrics: BaseHealthMetrics = Field(..., description="Health metrics")
    device_info: BaseDeviceInfo = Field(..., description="Device information")
    capabilities: BaseCapabilities = Field(..., description="Device capabilities")


# Platform-specific response schemas
class MacOSHealthResponse(BaseHealthResponse):
    """macOS specific health response with tracker info."""
    model_config = ConfigDict(extra="allow")

    system: BaseSystemInfo = Field(..., description="System information")
    tracker: dict[str, Any] | None = Field(None, description="Tracker status and info")
    deployment: dict[str, Any] | None = Field(None, description="Deployment information")
    display: dict[str, Any] | None = Field(None, description="Display information")


class OrangePiHealthResponse(BaseHealthResponse):
    """OrangePi specific health response with player and display info."""
    model_config = ConfigDict(extra="allow")

    player: dict[str, Any] | None = Field(None, description="Player status and info")
    deployment: dict[str, Any] | None = Field(None, description="Deployment information")
    display: dict[str, Any] | None = Field(None, description="Display information")


class StandardizedErrorResponse(BaseModel):
    """Standardized error response structure."""
    model_config = ConfigDict(extra="allow")

    status: str = Field(default="error", description="Response status")
    timestamp: str = Field(..., description="Error timestamp")
    timestamp_epoch: int = Field(..., description="Error timestamp epoch")
    error: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


# Legacy type aliases for backward compatibility
CPUMetrics = BaseCPUMetrics
MemoryMetrics = BaseMemoryMetrics
DiskMetrics = BaseDiskMetrics
NetworkMetrics = BaseNetworkMetrics
HealthMetrics = BaseHealthMetrics
SystemInfo = BaseSystemInfo
DeviceInfo = BaseDeviceInfo
VersionInfo = BaseVersionInfo
Capabilities = BaseCapabilities
