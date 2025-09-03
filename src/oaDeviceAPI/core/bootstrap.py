"""
Application bootstrap and dependency injection setup.

Handles the initialization of the dependency injection container and 
configuration of all services based on the detected platform.
"""

import logging
from typing import Dict, Any

from .container import container, ServiceContainer
from .service_factory import ServiceFactoryRegistry, setup_dependency_injection
from .interfaces import (
    PlatformManagerInterface,
    MetricsCollectorInterface,
    HealthServiceInterface,
    ConfigurationServiceInterface,
    CachingServiceInterface
)
from .unified_metrics import UnifiedMetricsCollector, MetricsFacade
from .health_service import UnifiedHealthService
from .caching import CacheManager
from .exceptions import ServiceError, ErrorSeverity
from .config import settings


logger = logging.getLogger(__name__)


class ApplicationBootstrap:
    """
    Handles application startup and dependency injection configuration.
    """

    def __init__(self):
        self.container: ServiceContainer = container
        self._initialized = False

    def initialize(self, platform_manager: PlatformManagerInterface) -> ServiceContainer:
        """
        Initialize the application with dependency injection.

        Args:
            platform_manager: Platform manager instance

        Returns:
            Configured service container

        Raises:
            ServiceError: If initialization fails
        """
        if self._initialized:
            logger.warning("Application already initialized")
            return self.container

        try:
            logger.info("Initializing application bootstrap...")

            # Step 1: Register core services
            self._register_core_services()

            # Step 2: Setup platform-specific dependency injection
            setup_dependency_injection(platform_manager)

            # Step 3: Configure unified services
            self._configure_unified_services()

            # Step 4: Validate service configuration
            self._validate_services()

            self._initialized = True
            logger.info("Application bootstrap completed successfully")
            
            return self.container

        except Exception as e:
            raise ServiceError(
                f"Failed to initialize application: {str(e)}",
                category="bootstrap",
                severity=ErrorSeverity.CRITICAL,
                recovery_suggestion="Check platform detection and service configuration"
            ) from e

    def _register_core_services(self) -> None:
        """Register core services that don't depend on platform."""
        logger.debug("Registering core services...")

        # Register cache manager
        cache_manager = CacheManager()
        self.container.register_instance(CachingServiceInterface, cache_manager)

        # Register configuration service (using existing settings)
        self.container.register_instance(ConfigurationServiceInterface, settings)

        logger.debug("Core services registered")

    def _configure_unified_services(self) -> None:
        """Configure unified services that wrap platform-specific implementations."""
        logger.debug("Configuring unified services...")

        # Get platform-specific metrics collector
        platform_collector = self.container.get(MetricsCollectorInterface)

        # Create unified metrics collector
        unified_collector = UnifiedMetricsCollector(platform_collector)
        
        # Create metrics facade
        metrics_facade = MetricsFacade(unified_collector)
        
        # Register metrics facade
        self.container.register_instance(MetricsFacade, metrics_facade)

        # Create and register unified health service
        health_service = UnifiedHealthService(metrics_facade)
        self.container.register_instance(HealthServiceInterface, health_service)

        logger.debug("Unified services configured")

    def _validate_services(self) -> None:
        """Validate that all required services are properly registered."""
        logger.debug("Validating service registration...")

        required_services = [
            PlatformManagerInterface,
            MetricsCollectorInterface,
            HealthServiceInterface,
            CachingServiceInterface,
            MetricsFacade
        ]

        missing_services = []
        for service_interface in required_services:
            if not self.container.is_registered(service_interface):
                missing_services.append(service_interface.__name__)

        if missing_services:
            raise ServiceError(
                f"Missing required services: {', '.join(missing_services)}",
                category="service_validation",
                severity=ErrorSeverity.CRITICAL
            )

        logger.debug("Service validation completed")

    def get_service_registry_info(self) -> Dict[str, Any]:
        """
        Get information about registered services.

        Returns:
            Dictionary with service registry information
        """
        registered_services = self.container.get_registered_services()
        
        return {
            'initialized': self._initialized,
            'registered_services': {
                interface.__name__: impl.__name__ 
                for interface, impl in registered_services.items()
            },
            'service_count': len(registered_services),
            'platform': getattr(
                self.container.get(PlatformManagerInterface) if self.container.is_registered(PlatformManagerInterface) else None,
                'platform', 
                'unknown'
            )
        }

    def reset(self) -> None:
        """Reset bootstrap state (useful for testing)."""
        self.container.clear()
        self._initialized = False
        logger.debug("Application bootstrap reset")


# Global bootstrap instance
bootstrap = ApplicationBootstrap()


def initialize_application(platform_manager: PlatformManagerInterface) -> ServiceContainer:
    """
    Initialize the application with dependency injection.

    Args:
        platform_manager: Platform manager instance

    Returns:
        Configured service container
    """
    return bootstrap.initialize(platform_manager)


def get_service_container() -> ServiceContainer:
    """Get the configured service container."""
    return bootstrap.container


def get_bootstrap_info() -> Dict[str, Any]:
    """Get bootstrap initialization information."""
    return bootstrap.get_service_registry_info()


# Decorator for dependency injection in route handlers
def inject_services(func):
    """
    Decorator for automatic dependency injection in route handlers.
    
    Usage:
        @inject_services
        async def health_endpoint(health_service: HealthServiceInterface):
            return await health_service.get_health_metrics()
    """
    return container.inject(func)