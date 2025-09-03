"""
Unified metrics collection system for oaDeviceAPI.

This module provides platform-agnostic metrics collection with
standardized interfaces and platform-specific implementations.
Eliminates code duplication between macOS and OrangePi metrics services.
"""

import platform
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Protocol, runtime_checkable

import psutil

from ..models.health_schemas import (
    BaseCPUMetrics,
    BaseMemoryMetrics,
    BaseDiskMetrics,
    BaseNetworkMetrics,
    BaseHealthMetrics,
    BaseSystemInfo,
    BaseDeviceInfo,
    BaseVersionInfo,
    MacOSCapabilities,
    OrangePiCapabilities
)
from .config import APP_VERSION
from .exceptions import MetricsCollectionError, ErrorSeverity
from .error_handler import ErrorHandler


@runtime_checkable
class PlatformMetricsProvider(Protocol):
    """Protocol for platform-specific metrics providers."""
    
    def get_version_info(self) -> Dict[str, Any]:
        """Get platform-specific version information."""
        ...
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get platform-specific device information."""
        ...
    
    def get_additional_cpu_info(self) -> Dict[str, Any]:
        """Get additional CPU information specific to platform."""
        ...
    
    def get_additional_system_info(self) -> Dict[str, Any]:
        """Get additional system information specific to platform."""
        ...
    
    def get_platform_capabilities(self) -> Dict[str, Any]:
        """Get platform-specific capabilities."""
        ...


class BaseMetricsCollector(ABC):
    """
    Abstract base class for metrics collection.
    
    Provides common functionality while allowing platform-specific
    implementations for specialized metrics.
    """
    
    def __init__(self, platform_provider: Optional[PlatformMetricsProvider] = None):
        self.platform_provider = platform_provider
        self._cache_ttl = 30  # seconds
        self._last_collection = {}
        self._cached_metrics = {}
    
    @ErrorHandler.handle_errors(convert_exceptions=True)
    def get_standardized_cpu_metrics(self) -> BaseCPUMetrics:
        """Get CPU metrics in standardized format."""
        try:
            # Get base CPU metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_cores = psutil.cpu_count()
            cpu_model = platform.processor()
            
            # Get platform-specific additional info
            additional_info = {}
            if self.platform_provider:
                additional_info = self.platform_provider.get_additional_cpu_info()
            
            # Use additional info if available
            if additional_info.get('model'):
                cpu_model = additional_info['model']
            
            return BaseCPUMetrics(
                usage_percent=cpu_usage,
                cores=cpu_cores,
                architecture=platform.machine(),
                model=cpu_model or "Unknown"
            )
        except Exception as exc:
            # Fallback with minimal data
            return BaseCPUMetrics(
                usage_percent=psutil.cpu_percent(interval=0.1),
                cores=psutil.cpu_count() or 1,
                architecture=platform.machine(),
                model="Unknown"
            )
    
    @ErrorHandler.handle_errors(convert_exceptions=True)
    def get_standardized_memory_metrics(self) -> BaseMemoryMetrics:
        """Get memory metrics in standardized format."""
        try:
            memory = psutil.virtual_memory()
            
            return BaseMemoryMetrics(
                usage_percent=memory.percent,
                total=memory.total,
                used=memory.used,
                available=memory.available,
                free=memory.free
            )
        except Exception as exc:
            raise MetricsCollectionError(
                "Failed to collect memory metrics",
                metric_type="memory",
                severity=ErrorSeverity.HIGH
            ) from exc
    
    @ErrorHandler.handle_errors(convert_exceptions=True)
    def get_standardized_disk_metrics(self, path: str = "/") -> BaseDiskMetrics:
        """Get disk metrics in standardized format."""
        try:
            disk = psutil.disk_usage(path)
            
            return BaseDiskMetrics(
                usage_percent=disk.percent,
                total=disk.total,
                used=disk.used,
                free=disk.free,
                path=path
            )
        except Exception as exc:
            raise MetricsCollectionError(
                f"Failed to collect disk metrics for path: {path}",
                metric_type="disk",
                severity=ErrorSeverity.HIGH
            ) from exc
    
    @ErrorHandler.handle_errors(convert_exceptions=True)
    def get_standardized_network_metrics(self) -> BaseNetworkMetrics:
        """Get network metrics in standardized format."""
        try:
            # Get network I/O counters
            net_io = psutil.net_io_counters()
            
            # Get interface statistics
            interfaces = {}
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters(pernic=True)
            
            for iface, stats in net_if_stats.items():
                interface_data = {
                    "up": stats.isup,
                    "speed": stats.speed,
                    "mtu": stats.mtu
                }
                
                # Add I/O stats if available
                if iface in net_io_counters:
                    io_stats = net_io_counters[iface]
                    interface_data.update({
                        "bytes_sent": io_stats.bytes_sent,
                        "bytes_received": io_stats.bytes_recv,
                        "packets_sent": io_stats.packets_sent,
                        "packets_received": io_stats.packets_recv
                    })
                
                interfaces[iface] = interface_data
            
            return BaseNetworkMetrics(
                bytes_sent=net_io.bytes_sent if net_io else 0,
                bytes_received=net_io.bytes_recv if net_io else 0,
                packets_sent=net_io.packets_sent if net_io else 0,
                packets_received=net_io.packets_recv if net_io else 0,
                interfaces=interfaces
            )
        except Exception as exc:
            raise MetricsCollectionError(
                "Failed to collect network metrics",
                metric_type="network",
                severity=ErrorSeverity.MEDIUM
            ) from exc
    
    def get_standardized_system_info(self) -> BaseSystemInfo:
        """Get system information in standardized format."""
        try:
            # Get base system info
            base_info = {
                "platform": platform.system(),
                "architecture": platform.machine(),
                "hostname": platform.node(),
                "uptime": psutil.boot_time()
            }
            
            # Get platform-specific additional info
            if self.platform_provider:
                additional_info = self.platform_provider.get_additional_system_info()
                base_info.update(additional_info)
            
            return BaseSystemInfo(
                platform=base_info.get("platform", "Unknown"),
                architecture=base_info.get("architecture", "Unknown"),
                hostname=base_info.get("hostname", "Unknown"),
                uptime=base_info.get("uptime", 0),
                **{k: v for k, v in base_info.items() 
                   if k not in ["platform", "architecture", "hostname", "uptime"]}
            )
        except Exception as exc:
            raise MetricsCollectionError(
                "Failed to collect system information",
                metric_type="system_info",
                severity=ErrorSeverity.HIGH
            ) from exc
    
    def get_standardized_device_info(self) -> BaseDeviceInfo:
        """Get device information in standardized format."""
        try:
            # Get base device info
            device_info = {
                "type": "Unknown",
                "series": "Unknown",
                "hostname": platform.node(),
                "model": "Unknown"
            }
            
            # Get platform-specific device info
            if self.platform_provider:
                platform_device_info = self.platform_provider.get_device_info()
                device_info.update(platform_device_info)
            
            return BaseDeviceInfo(**device_info)
        except Exception as exc:
            raise MetricsCollectionError(
                "Failed to collect device information",
                metric_type="device_info",
                severity=ErrorSeverity.MEDIUM
            ) from exc
    
    def get_standardized_version_info(self) -> BaseVersionInfo:
        """Get version information in standardized format."""
        try:
            # Get base version info
            version_info = {
                "api_version": APP_VERSION,
                "python_version": platform.python_version(),
                "os_version": platform.platform()
            }
            
            # Get platform-specific version info
            if self.platform_provider:
                platform_version_info = self.platform_provider.get_version_info()
                version_info.update(platform_version_info)
            
            return BaseVersionInfo(**version_info)
        except Exception as exc:
            raise MetricsCollectionError(
                "Failed to collect version information",
                metric_type="version_info",
                severity=ErrorSeverity.MEDIUM
            ) from exc
    
    @abstractmethod
    def get_platform_capabilities(self) -> Dict[str, Any]:
        """Get platform-specific capabilities."""
        pass
    
    def get_complete_health_metrics(self) -> BaseHealthMetrics:
        """Get complete health metrics in standardized format."""
        try:
            return BaseHealthMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu=self.get_standardized_cpu_metrics(),
                memory=self.get_standardized_memory_metrics(),
                disk=self.get_standardized_disk_metrics(),
                network=self.get_standardized_network_metrics(),
                system_info=self.get_standardized_system_info(),
                device_info=self.get_standardized_device_info(),
                version_info=self.get_standardized_version_info(),
                capabilities=self.get_platform_capabilities()
            )
        except Exception as exc:
            raise MetricsCollectionError(
                "Failed to collect complete health metrics",
                severity=ErrorSeverity.CRITICAL
            ) from exc


class MacOSMetricsCollector(BaseMetricsCollector):
    """macOS-specific metrics collector."""
    
    def __init__(self, platform_provider: Optional[PlatformMetricsProvider] = None):
        super().__init__(platform_provider)
    
    def get_platform_capabilities(self) -> MacOSCapabilities:
        """Get macOS-specific capabilities."""
        capabilities_data = {
            "screenshot_supported": False,
            "camera_supported": True,
            "tracker_supported": True,
            "camguard_supported": True,
            "display_management": True,
            "service_management": "launchctl",
            "temperature_monitoring": True
        }
        
        # Get additional capabilities from provider
        if self.platform_provider:
            additional_caps = self.platform_provider.get_platform_capabilities()
            capabilities_data.update(additional_caps)
        
        return MacOSCapabilities(**capabilities_data)


class OrangePiMetricsCollector(BaseMetricsCollector):
    """OrangePi-specific metrics collector."""
    
    def __init__(self, platform_provider: Optional[PlatformMetricsProvider] = None):
        super().__init__(platform_provider)
    
    def get_platform_capabilities(self) -> OrangePiCapabilities:
        """Get OrangePi-specific capabilities."""
        capabilities_data = {
            "screenshot_supported": True,
            "camera_supported": False,
            "tracker_supported": False,
            "camguard_supported": False,
            "display_management": True,
            "service_management": "systemctl",
            "player_supported": True,
            "gpio_supported": True
        }
        
        # Get additional capabilities from provider
        if self.platform_provider:
            additional_caps = self.platform_provider.get_platform_capabilities()
            capabilities_data.update(additional_caps)
        
        return OrangePiCapabilities(**capabilities_data)


class MetricsCollectorFactory:
    """Factory for creating platform-specific metrics collectors."""
    
    _collectors = {
        "macos": MacOSMetricsCollector,
        "orangepi": OrangePiMetricsCollector
    }
    
    @classmethod
    def create_collector(
        self,
        platform: str,
        provider: Optional[PlatformMetricsProvider] = None
    ) -> BaseMetricsCollector:
        """Create a metrics collector for the specified platform."""
        collector_class = self._collectors.get(platform.lower())
        if not collector_class:
            # Fall back to base collector for unknown platforms
            return BaseMetricsCollector(provider)
        
        return collector_class(provider)
    
    @classmethod
    def register_collector(
        cls, 
        platform: str, 
        collector_class: type[BaseMetricsCollector]
    ) -> None:
        """Register a new metrics collector for a platform."""
        cls._collectors[platform.lower()] = collector_class


# Global metrics collector instance (will be initialized by platform detection)
_metrics_collector: Optional[BaseMetricsCollector] = None


def get_metrics_collector() -> BaseMetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    
    if _metrics_collector is None:
        from .platform import platform_manager
        _metrics_collector = MetricsCollectorFactory.create_collector(
            platform_manager.platform
        )
    
    return _metrics_collector


def set_metrics_collector(collector: BaseMetricsCollector) -> None:
    """Set the global metrics collector instance (mainly for testing)."""
    global _metrics_collector
    _metrics_collector = collector