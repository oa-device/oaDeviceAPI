"""
Standardized Health Data Schemas

Shared Pydantic models for device health data across all oaPangaea components.
These schemas ensure consistent data structures between device APIs and oaDashboard.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class BaseCPUMetrics(BaseModel):
    """Standardized CPU metrics structure."""
    
    usage_percent: float = Field(..., description="CPU usage percentage (0-100)")
    cores: int = Field(..., description="Number of CPU cores")
    architecture: Optional[str] = Field(None, description="CPU architecture (e.g., arm64, x86_64)")
    model: Optional[str] = Field(None, description="CPU model name")
    
    class Config:
        extra = "allow"


class BaseMemoryMetrics(BaseModel):
    """Standardized memory metrics structure."""
    
    usage_percent: float = Field(..., description="Memory usage percentage (0-100)")
    total: int = Field(..., description="Total memory in bytes")
    used: int = Field(..., description="Used memory in bytes")
    available: int = Field(..., description="Available memory in bytes")
    
    class Config:
        extra = "allow"


class BaseDiskMetrics(BaseModel):
    """Standardized disk metrics structure."""
    
    usage_percent: float = Field(..., description="Disk usage percentage (0-100)")
    total: int = Field(..., description="Total disk space in bytes")
    used: int = Field(..., description="Used disk space in bytes")
    free: int = Field(..., description="Free disk space in bytes")
    path: Optional[str] = Field("/", description="Disk mount path")
    
    class Config:
        extra = "allow"


class BaseNetworkMetrics(BaseModel):
    """Standardized network metrics structure."""
    
    bytes_sent: int = Field(..., description="Total bytes sent")
    bytes_received: int = Field(..., description="Total bytes received")
    packets_sent: int = Field(..., description="Total packets sent")
    packets_received: int = Field(..., description="Total packets received")
    interface: Optional[str] = Field(None, description="Network interface name")
    
    class Config:
        extra = "allow"


class BaseHealthMetrics(BaseModel):
    """Standardized base health metrics structure."""
    
    cpu: BaseCPUMetrics = Field(..., description="CPU metrics")
    memory: BaseMemoryMetrics = Field(..., description="Memory metrics")
    disk: BaseDiskMetrics = Field(..., description="Disk metrics") 
    network: BaseNetworkMetrics = Field(..., description="Network metrics")
    
    class Config:
        extra = "allow"


class BaseSystemInfo(BaseModel):
    """Standardized system information structure."""
    
    os_version: str = Field(..., description="Operating system version")
    kernel_version: Optional[str] = Field(None, description="Kernel version")
    hostname: str = Field(..., description="System hostname")
    uptime: Optional[float] = Field(None, description="System uptime in seconds")
    uptime_human: Optional[str] = Field(None, description="Human-readable uptime")
    boot_time: Optional[float] = Field(None, description="Boot timestamp (Unix)")
    architecture: Optional[str] = Field(None, description="System architecture")
    
    class Config:
        extra = "allow"


class BaseDeviceInfo(BaseModel):
    """Standardized device information structure."""
    
    type: str = Field(..., description="Device type (Mac, OrangePi, etc.)")
    series: Optional[str] = Field(None, description="Device series")
    hostname: str = Field(..., description="Device hostname")
    model: Optional[str] = Field(None, description="Device model")
    
    class Config:
        extra = "allow"


class BaseVersionInfo(BaseModel):
    """Standardized version information structure."""
    
    api: str = Field(..., description="API version")
    python: str = Field(..., description="Python version")
    tailscale: Optional[str] = Field(None, description="Tailscale version")
    system: Dict[str, str] = Field(..., description="System version information")
    
    class Config:
        extra = "allow"


class BaseCapabilities(BaseModel):
    """Standardized device capabilities structure."""
    
    supports_reboot: bool = Field(True, description="Device supports reboot")
    supports_ssh: bool = Field(True, description="Device supports SSH")
    
    class Config:
        extra = "allow"


# Platform-specific extensions

class MacOSCapabilities(BaseCapabilities):
    """macOS-specific capabilities."""
    
    supports_camera_stream: bool = Field(True, description="Device supports camera streaming")
    supports_tracker_restart: bool = Field(True, description="Device supports tracker restart")
    device_has_camera_support: bool = Field(True, description="Device has camera hardware")


class OrangePiCapabilities(BaseCapabilities):
    """OrangePi-specific capabilities."""
    
    supports_screenshots: bool = Field(True, description="Device supports screenshots")
    supports_player_restart: bool = Field(True, description="Device supports player restart")
    supports_display_setup: bool = Field(True, description="Device supports display setup")
    device_has_camera_support: bool = Field(False, description="Device has camera hardware")


# Health response base structure

class BaseHealthResponse(BaseModel):
    """Standardized base health response structure."""
    
    status: str = Field(..., description="Overall device status (online, offline, maintenance)")
    hostname: str = Field(..., description="Device hostname")
    timestamp: str = Field(..., description="Response timestamp (ISO format)")
    timestamp_epoch: int = Field(..., description="Response timestamp (Unix epoch)")
    version: BaseVersionInfo = Field(..., description="Version information")
    metrics: BaseHealthMetrics = Field(..., description="System metrics")
    device_info: BaseDeviceInfo = Field(..., description="Device information")
    capabilities: BaseCapabilities = Field(..., description="Device capabilities")
    
    class Config:
        extra = "allow"


# Platform-specific health responses

class MacOSHealthResponse(BaseHealthResponse):
    """macOS-specific health response structure."""
    
    capabilities: MacOSCapabilities = Field(..., description="macOS capabilities")
    deployment: Dict[str, Any] = Field(default_factory=dict, description="Deployment information")
    tracker: Dict[str, Any] = Field(default_factory=dict, description="Tracker status")
    system: BaseSystemInfo = Field(..., description="System information")
    display: Dict[str, Any] = Field(default_factory=dict, description="Display information")


class OrangePiHealthResponse(BaseHealthResponse):
    """OrangePi-specific health response structure."""
    
    capabilities: OrangePiCapabilities = Field(..., description="OrangePi capabilities")
    deployment: Dict[str, Any] = Field(default_factory=dict, description="Deployment information")
    player: Dict[str, Any] = Field(default_factory=dict, description="Player status")
    display: Dict[str, Any] = Field(default_factory=dict, description="Display information")


# Error response structure

class StandardizedErrorResponse(BaseModel):
    """Standardized error response structure."""
    
    status: str = Field("error", description="Status indicator")
    timestamp: str = Field(..., description="Error timestamp (ISO format)")
    timestamp_epoch: int = Field(..., description="Error timestamp (Unix epoch)")
    error: str = Field(..., description="Error message")
    
    class Config:
        extra = "allow"