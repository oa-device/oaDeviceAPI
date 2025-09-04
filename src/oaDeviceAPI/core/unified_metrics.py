"""
Unified metrics collection system.

Consolidates metrics collection across platforms, eliminating code duplication
and providing a consistent interface for health monitoring and system metrics.
"""

from abc import ABC, abstractmethod
from typing import Any

from .caching import CacheManager
from .exceptions import ErrorSeverity, ServiceError
from .interfaces import BaseMetricsCollector, MetricsCollectorInterface


class UnifiedMetricsCollector(BaseMetricsCollector):
    """
    Unified metrics collector that delegates to platform-specific implementations
    while providing consistent caching and error handling.
    """

    def __init__(self, platform_collector: MetricsCollectorInterface):
        """
        Initialize with platform-specific collector.

        Args:
            platform_collector: Platform-specific metrics implementation
        """
        self.platform_collector = platform_collector
        self.cache_manager = CacheManager()

    @CacheManager().cache_with_ttl(ttl=30)  # Cache for 30 seconds
    async def collect_cpu_metrics(self) -> dict[str, Any]:
        """Collect CPU metrics with caching."""
        try:
            return await self.platform_collector.collect_cpu_metrics()
        except Exception as e:
            raise ServiceError(
                f"Failed to collect CPU metrics: {str(e)}",
                category="metrics_collection",
                severity=ErrorSeverity.MEDIUM
            ) from e

    @CacheManager().cache_with_ttl(ttl=30)
    async def collect_memory_metrics(self) -> dict[str, Any]:
        """Collect memory metrics with caching."""
        try:
            return await self.platform_collector.collect_memory_metrics()
        except Exception as e:
            raise ServiceError(
                f"Failed to collect memory metrics: {str(e)}",
                category="metrics_collection",
                severity=ErrorSeverity.MEDIUM
            ) from e

    @CacheManager().cache_with_ttl(ttl=60)  # Disk metrics change less frequently
    async def collect_disk_metrics(self) -> dict[str, Any]:
        """Collect disk metrics with caching."""
        try:
            return await self.platform_collector.collect_disk_metrics()
        except Exception as e:
            raise ServiceError(
                f"Failed to collect disk metrics: {str(e)}",
                category="metrics_collection",
                severity=ErrorSeverity.MEDIUM
            ) from e

    async def collect_all_metrics(self) -> dict[str, Any]:
        """
        Collect all metrics concurrently for better performance.

        Returns:
            Dictionary containing all metrics with error handling
        """
        results = {}

        # Collect metrics concurrently
        tasks = {
            'cpu': self.collect_cpu_metrics(),
            'memory': self.collect_memory_metrics(),
            'disk': self.collect_disk_metrics(),
        }

        # Wait for all tasks with individual error handling
        for metric_type, task in tasks.items():
            try:
                results[metric_type] = await task
            except Exception as e:
                # Log error but continue with other metrics
                results[metric_type] = {
                    'error': str(e),
                    'available': False
                }

        return results

    async def get_health_summary(self) -> dict[str, Any]:
        """
        Get high-level health summary based on all metrics.

        Returns:
            Health summary with status indicators
        """
        metrics = await self.collect_all_metrics()

        summary = {
            'overall_status': 'healthy',
            'issues': [],
            'metrics_collected': len([m for m in metrics.values() if not m.get('error')]),
            'total_metrics': len(metrics)
        }

        # Analyze CPU health
        if 'cpu' in metrics and not metrics['cpu'].get('error'):
            cpu_usage = metrics['cpu'].get('usage_percent', 0)
            if cpu_usage > 90:
                summary['issues'].append('High CPU usage')
                summary['overall_status'] = 'warning'

        # Analyze memory health
        if 'memory' in metrics and not metrics['memory'].get('error'):
            memory_usage = metrics['memory'].get('usage_percent', 0)
            if memory_usage > 85:
                summary['issues'].append('High memory usage')
                summary['overall_status'] = 'warning'

        # Analyze disk health
        if 'disk' in metrics and not metrics['disk'].get('error'):
            disk_usage = metrics['disk'].get('usage_percent', 0)
            if disk_usage > 90:
                summary['issues'].append('High disk usage')
                if disk_usage > 95:
                    summary['overall_status'] = 'critical'

        return summary


class MetricsFacade:
    """
    Facade pattern for simplified metrics access across the application.

    Provides a single entry point for all metrics operations with consistent
    error handling and caching behavior.
    """

    def __init__(self, metrics_collector: UnifiedMetricsCollector):
        """
        Initialize facade with metrics collector.

        Args:
            metrics_collector: Unified metrics collector instance
        """
        self.collector = metrics_collector

    async def get_system_metrics(self) -> dict[str, Any]:
        """Get all system metrics."""
        return await self.collector.collect_all_metrics()

    async def get_cpu_info(self) -> dict[str, Any]:
        """Get CPU information and usage."""
        return await self.collector.collect_cpu_metrics()

    async def get_memory_info(self) -> dict[str, Any]:
        """Get memory information and usage."""
        return await self.collector.collect_memory_metrics()

    async def get_disk_info(self) -> dict[str, Any]:
        """Get disk information and usage."""
        return await self.collector.collect_disk_metrics()

    async def get_health_status(self) -> dict[str, Any]:
        """Get overall system health status."""
        return await self.collector.get_health_summary()

    async def is_system_healthy(self) -> bool:
        """
        Quick health check.

        Returns:
            True if system is healthy, False otherwise
        """
        try:
            health = await self.collector.get_health_summary()
            return health['overall_status'] in ['healthy', 'warning']
        except Exception:
            return False


# Strategy pattern for platform-specific metrics behavior
class MetricsStrategy(ABC):
    """Abstract strategy for platform-specific metrics collection."""

    @abstractmethod
    async def get_platform_specific_metrics(self) -> dict[str, Any]:
        """Get metrics specific to the platform."""
        pass

    @abstractmethod
    def get_supported_metrics(self) -> list[str]:
        """Get list of supported metric types for this platform."""
        pass


class MacOSMetricsStrategy(MetricsStrategy):
    """macOS-specific metrics collection strategy."""

    async def get_platform_specific_metrics(self) -> dict[str, Any]:
        """Get macOS-specific metrics like SMC data."""
        return {
            'temperature_sensors': await self._get_temperature_data(),
            'power_management': await self._get_power_info(),
            'system_profile': await self._get_system_profile()
        }

    def get_supported_metrics(self) -> list[str]:
        """Metrics supported on macOS."""
        return ['cpu', 'memory', 'disk', 'temperature', 'power', 'system_profile']

    async def _get_temperature_data(self) -> dict[str, Any]:
        """Get temperature sensor data via SMC."""
        # Implementation would use SMC commands
        return {'available': True}  # Placeholder

    async def _get_power_info(self) -> dict[str, Any]:
        """Get power management information."""
        # Implementation would use pmset or system_profiler
        return {'available': True}  # Placeholder

    async def _get_system_profile(self) -> dict[str, Any]:
        """Get system profile information."""
        # Implementation would use system_profiler
        return {'available': True}  # Placeholder


class OrangePiMetricsStrategy(MetricsStrategy):
    """OrangePi-specific metrics collection strategy."""

    async def get_platform_specific_metrics(self) -> dict[str, Any]:
        """Get OrangePi-specific metrics."""
        return {
            'gpio_status': await self._get_gpio_info(),
            'thermal_zones': await self._get_thermal_info(),
            'hardware_info': await self._get_hardware_info()
        }

    def get_supported_metrics(self) -> list[str]:
        """Metrics supported on OrangePi."""
        return ['cpu', 'memory', 'disk', 'gpio', 'thermal', 'hardware']

    async def _get_gpio_info(self) -> dict[str, Any]:
        """Get GPIO status information."""
        # Implementation would read GPIO status
        return {'available': True}  # Placeholder

    async def _get_thermal_info(self) -> dict[str, Any]:
        """Get thermal zone information."""
        # Implementation would read /sys/class/thermal
        return {'available': True}  # Placeholder

    async def _get_hardware_info(self) -> dict[str, Any]:
        """Get hardware-specific information."""
        # Implementation would read hardware specs
        return {'available': True}  # Placeholder
