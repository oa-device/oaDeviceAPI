"""
Service interfaces for oaDeviceAPI dependency injection.

Defines protocol interfaces for all major services to enable loose coupling
and testability through dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from ..models.health_schemas import BaseHealthMetrics as HealthMetrics
from ..models.health_schemas import BaseSystemInfo as SystemInfo


class HealthServiceInterface(Protocol):
    """Protocol for health monitoring services."""

    async def get_health_metrics(self) -> HealthMetrics:
        """Get current system health metrics."""
        ...

    async def get_system_info(self) -> SystemInfo:
        """Get system information."""
        ...

    async def is_healthy(self) -> bool:
        """Check if system is in healthy state."""
        ...


class MetricsCollectorInterface(Protocol):
    """Protocol for metrics collection services."""

    async def collect_cpu_metrics(self) -> dict[str, Any]:
        """Collect CPU usage metrics."""
        ...

    async def collect_memory_metrics(self) -> dict[str, Any]:
        """Collect memory usage metrics."""
        ...

    async def collect_disk_metrics(self) -> dict[str, Any]:
        """Collect disk usage metrics."""
        ...

    async def collect_all_metrics(self) -> dict[str, Any]:
        """Collect all available metrics."""
        ...


class PlatformManagerInterface(Protocol):
    """Protocol for platform management services."""

    @property
    def platform(self) -> str:
        """Get current platform identifier."""
        ...

    @property
    def config(self) -> dict[str, Any]:
        """Get platform-specific configuration."""
        ...

    def is_macos(self) -> bool:
        """Check if running on macOS."""
        ...

    def is_linux(self) -> bool:
        """Check if running on Linux."""
        ...

    def get_service_manager(self) -> str:
        """Get the service manager name for this platform."""
        ...


class ServiceControllerInterface(Protocol):
    """Protocol for service control operations."""

    async def restart_service(self, service_name: str) -> dict[str, Any]:
        """Restart a system service."""
        ...

    async def get_service_status(self, service_name: str) -> dict[str, Any]:
        """Get status of a system service."""
        ...

    async def start_service(self, service_name: str) -> dict[str, Any]:
        """Start a system service."""
        ...

    async def stop_service(self, service_name: str) -> dict[str, Any]:
        """Stop a system service."""
        ...


class TrackerServiceInterface(Protocol):
    """Protocol for tracker service integration."""

    async def get_tracker_stats(self) -> dict[str, Any]:
        """Get tracker statistics."""
        ...

    async def get_tracker_status(self) -> dict[str, Any]:
        """Get tracker service status."""
        ...

    def is_available(self) -> bool:
        """Check if tracker service is available."""
        ...


class CameraServiceInterface(Protocol):
    """Protocol for camera service operations."""

    async def get_camera_info(self) -> dict[str, Any]:
        """Get camera information."""
        ...

    async def capture_image(self) -> bytes | None:
        """Capture image from camera."""
        ...

    def is_available(self) -> bool:
        """Check if camera is available."""
        ...


class ScreenshotServiceInterface(Protocol):
    """Protocol for screenshot services."""

    async def capture_screenshot(self) -> bytes | None:
        """Capture screenshot."""
        ...

    def is_supported(self) -> bool:
        """Check if screenshots are supported on this platform."""
        ...


class ConfigurationServiceInterface(Protocol):
    """Protocol for configuration management."""

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        ...

    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value."""
        ...

    def get_platform_config(self) -> dict[str, Any]:
        """Get platform-specific configuration."""
        ...

    def validate_config(self) -> dict[str, Any]:
        """Validate current configuration."""
        ...


class LoggingServiceInterface(Protocol):
    """Protocol for logging services."""

    def get_logger(self, name: str):
        """Get logger instance for given name."""
        ...

    def configure_logging(self, config: dict[str, Any]) -> None:
        """Configure logging system."""
        ...

    def get_log_level(self) -> str:
        """Get current log level."""
        ...


class CachingServiceInterface(Protocol):
    """Protocol for caching services."""

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with optional TTL."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        ...

    async def clear(self) -> None:
        """Clear all cache entries."""
        ...


# Abstract base classes for common implementations

class BaseHealthService(ABC):
    """Abstract base class for health services."""

    @abstractmethod
    async def get_health_metrics(self) -> HealthMetrics:
        """Get current system health metrics."""
        pass

    @abstractmethod
    async def get_system_info(self) -> SystemInfo:
        """Get system information."""
        pass

    async def is_healthy(self) -> bool:
        """Default implementation of health check."""
        try:
            await self.get_health_metrics()
            # Consider system healthy if no critical issues
            return True  # Implement specific logic based on metrics
        except Exception:
            return False


class BaseMetricsCollector(ABC):
    """Abstract base class for metrics collectors."""

    @abstractmethod
    async def collect_cpu_metrics(self) -> dict[str, Any]:
        """Collect CPU usage metrics."""
        pass

    @abstractmethod
    async def collect_memory_metrics(self) -> dict[str, Any]:
        """Collect memory usage metrics."""
        pass

    @abstractmethod
    async def collect_disk_metrics(self) -> dict[str, Any]:
        """Collect disk usage metrics."""
        pass

    async def collect_all_metrics(self) -> dict[str, Any]:
        """Default implementation that combines all metrics."""
        return {
            "cpu": await self.collect_cpu_metrics(),
            "memory": await self.collect_memory_metrics(),
            "disk": await self.collect_disk_metrics(),
        }


class BaseServiceController(ABC):
    """Abstract base class for service controllers."""

    def __init__(self, platform_manager: PlatformManagerInterface):
        self.platform_manager = platform_manager

    @abstractmethod
    async def restart_service(self, service_name: str) -> dict[str, Any]:
        """Restart a system service."""
        pass

    @abstractmethod
    async def get_service_status(self, service_name: str) -> dict[str, Any]:
        """Get status of a system service."""
        pass

    @abstractmethod
    async def start_service(self, service_name: str) -> dict[str, Any]:
        """Start a system service."""
        pass

    @abstractmethod
    async def stop_service(self, service_name: str) -> dict[str, Any]:
        """Stop a system service."""
        pass
