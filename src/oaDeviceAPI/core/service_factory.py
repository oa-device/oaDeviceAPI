"""
Service factory for creating platform-specific service implementations.

Provides a factory pattern for creating and configuring services based on
the detected platform, enabling clean separation between platform-agnostic
interfaces and platform-specific implementations.
"""

from abc import ABC, abstractmethod

from .container import ServiceContainer
from .exceptions import ErrorSeverity, ServiceError
from .interfaces import (
    CameraServiceInterface,
    HealthServiceInterface,
    MetricsCollectorInterface,
    PlatformManagerInterface,
    ScreenshotServiceInterface,
    ServiceControllerInterface,
    TrackerServiceInterface,
)


class ServiceFactory(ABC):
    """Abstract factory for creating platform-specific services."""

    def __init__(self, platform_manager: PlatformManagerInterface):
        self.platform_manager = platform_manager

    @abstractmethod
    def create_health_service(self) -> HealthServiceInterface:
        """Create platform-specific health service."""
        pass

    @abstractmethod
    def create_metrics_collector(self) -> MetricsCollectorInterface:
        """Create platform-specific metrics collector."""
        pass

    @abstractmethod
    def create_service_controller(self) -> ServiceControllerInterface:
        """Create platform-specific service controller."""
        pass

    @abstractmethod
    def create_tracker_service(self) -> TrackerServiceInterface:
        """Create platform-specific tracker service."""
        pass

    @abstractmethod
    def create_camera_service(self) -> CameraServiceInterface:
        """Create platform-specific camera service."""
        pass

    @abstractmethod
    def create_screenshot_service(self) -> ScreenshotServiceInterface:
        """Create platform-specific screenshot service."""
        pass

    def register_all_services(self, container: ServiceContainer) -> None:
        """Register all services with the DI container."""
        container.register(HealthServiceInterface, type(self.create_health_service()))
        container.register(MetricsCollectorInterface, type(self.create_metrics_collector()))
        container.register(ServiceControllerInterface, type(self.create_service_controller()))
        container.register(TrackerServiceInterface, type(self.create_tracker_service()))
        container.register(CameraServiceInterface, type(self.create_camera_service()))
        container.register(ScreenshotServiceInterface, type(self.create_screenshot_service()))


class MacOSServiceFactory(ServiceFactory):
    """Factory for creating macOS-specific services."""

    def create_health_service(self) -> HealthServiceInterface:
        """Create macOS health service."""
        from ..platforms.macos.services.health_service import MacOSHealthService
        return MacOSHealthService(
            metrics_collector=self.create_metrics_collector()
        )

    def create_metrics_collector(self) -> MetricsCollectorInterface:
        """Create macOS metrics collector."""
        from ..platforms.macos.services.metrics_provider import MacOSMetricsProvider
        return MacOSMetricsProvider()

    def create_service_controller(self) -> ServiceControllerInterface:
        """Create macOS service controller."""
        from ..platforms.macos.services.service_controller import MacOSServiceController
        return MacOSServiceController(self.platform_manager)

    def create_tracker_service(self) -> TrackerServiceInterface:
        """Create macOS tracker service."""
        from ..platforms.macos.services.tracker_service import MacOSTrackerService
        return MacOSTrackerService()

    def create_camera_service(self) -> CameraServiceInterface:
        """Create macOS camera service."""
        from ..platforms.macos.services.camera_service import MacOSCameraService
        return MacOSCameraService()

    def create_screenshot_service(self) -> ScreenshotServiceInterface:
        """Create macOS screenshot service (not supported)."""
        from ..platforms.macos.services.screenshot_service import MacOSScreenshotService
        return MacOSScreenshotService()


class OrangePiServiceFactory(ServiceFactory):
    """Factory for creating OrangePi-specific services."""

    def create_health_service(self) -> HealthServiceInterface:
        """Create OrangePi health service."""
        from ..platforms.orangepi.services.health_service import OrangePiHealthService
        return OrangePiHealthService(
            metrics_collector=self.create_metrics_collector()
        )

    def create_metrics_collector(self) -> MetricsCollectorInterface:
        """Create OrangePi metrics collector."""
        from ..platforms.orangepi.services.metrics_provider import (
            OrangePiMetricsProvider,
        )
        return OrangePiMetricsProvider()

    def create_service_controller(self) -> ServiceControllerInterface:
        """Create OrangePi service controller."""
        from ..platforms.orangepi.services.service_controller import (
            OrangePiServiceController,
        )
        return OrangePiServiceController(self.platform_manager)

    def create_tracker_service(self) -> TrackerServiceInterface:
        """Create OrangePi tracker service (not available)."""
        from ..platforms.orangepi.services.tracker_service import OrangePiTrackerService
        return OrangePiTrackerService()

    def create_camera_service(self) -> CameraServiceInterface:
        """Create OrangePi camera service (not available)."""
        from ..platforms.orangepi.services.camera_service import OrangePiCameraService
        return OrangePiCameraService()

    def create_screenshot_service(self) -> ScreenshotServiceInterface:
        """Create OrangePi screenshot service."""
        from ..platforms.orangepi.services.screenshot_service import (
            OrangePiScreenshotService,
        )
        return OrangePiScreenshotService()


class ServiceFactoryRegistry:
    """Registry for managing service factories by platform."""

    _factories: dict[str, type[ServiceFactory]] = {
        "macos": MacOSServiceFactory,
        "orangepi": OrangePiServiceFactory,
        "linux": OrangePiServiceFactory,  # Fallback for generic Linux
    }

    @classmethod
    def get_factory(cls, platform: str, platform_manager: PlatformManagerInterface) -> ServiceFactory:
        """
        Get appropriate service factory for platform.

        Args:
            platform: Platform identifier
            platform_manager: Platform manager instance

        Returns:
            Service factory instance

        Raises:
            ServiceError: If platform is not supported
        """
        if platform.lower() not in cls._factories:
            raise ServiceError(
                f"Unsupported platform: {platform}",
                category="platform_detection",
                severity=ErrorSeverity.HIGH
            )

        factory_class = cls._factories[platform.lower()]
        return factory_class(platform_manager)

    @classmethod
    def register_factory(cls, platform: str, factory_class: type[ServiceFactory]) -> None:
        """Register a custom service factory for a platform."""
        cls._factories[platform.lower()] = factory_class

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Get list of supported platforms."""
        return list(cls._factories.keys())


def setup_dependency_injection(platform_manager: PlatformManagerInterface) -> ServiceContainer:
    """
    Setup dependency injection container with platform-specific services.

    Args:
        platform_manager: Platform manager instance

    Returns:
        Configured service container
    """
    from .container import container

    # Register platform manager
    container.register_instance(PlatformManagerInterface, platform_manager)

    # Get platform-specific factory
    factory = ServiceFactoryRegistry.get_factory(
        platform_manager.platform,
        platform_manager
    )

    # Register all platform-specific services
    factory.register_all_services(container)

    return container
