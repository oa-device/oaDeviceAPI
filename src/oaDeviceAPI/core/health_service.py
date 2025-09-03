"""
Unified health service with dependency injection.

Provides a platform-agnostic health monitoring service that uses dependency
injection for metrics collection and follows clean architecture principles.
"""

from typing import Dict, Any
import asyncio
from datetime import datetime, timezone

from .interfaces import HealthServiceInterface, MetricsCollectorInterface, BaseHealthService
from .unified_metrics import MetricsFacade
from .exceptions import ServiceError, ErrorSeverity
from ..models.health_schemas import HealthMetrics, SystemInfo


class UnifiedHealthService(BaseHealthService):
    """
    Unified health service that provides consistent health monitoring
    across all platforms using dependency injection.
    """

    def __init__(self, metrics_facade: MetricsFacade):
        """
        Initialize health service with metrics facade.

        Args:
            metrics_facade: Metrics facade for collecting system metrics
        """
        self.metrics_facade = metrics_facade
        self._last_health_check = None
        self._cached_health_metrics = None

    async def get_health_metrics(self) -> HealthMetrics:
        """
        Get comprehensive health metrics.

        Returns:
            HealthMetrics object with current system health data
        """
        try:
            # Get all system metrics
            metrics_data = await self.metrics_facade.get_system_metrics()
            
            # Convert to structured health metrics
            health_metrics = HealthMetrics(
                cpu=self._extract_cpu_metrics(metrics_data.get('cpu', {})),
                memory=self._extract_memory_metrics(metrics_data.get('memory', {})),
                disk=self._extract_disk_metrics(metrics_data.get('disk', {})),
                timestamp=datetime.now(timezone.utc),
                overall_health=await self._calculate_overall_health(metrics_data)
            )

            # Cache successful result
            self._cached_health_metrics = health_metrics
            self._last_health_check = datetime.now(timezone.utc)

            return health_metrics

        except Exception as e:
            # Return cached data if available, otherwise raise
            if self._cached_health_metrics:
                return self._cached_health_metrics
            
            raise ServiceError(
                f"Failed to collect health metrics: {str(e)}",
                category="health_monitoring",
                severity=ErrorSeverity.HIGH,
                recovery_suggestion="Check system metrics collection services"
            ) from e

    async def get_system_info(self) -> SystemInfo:
        """
        Get system information.

        Returns:
            SystemInfo object with system details
        """
        try:
            metrics_data = await self.metrics_facade.get_system_metrics()
            
            return SystemInfo(
                platform=self._get_platform_info(),
                uptime=self._get_system_uptime(),
                load_average=metrics_data.get('cpu', {}).get('load_average', []),
                cpu_count=metrics_data.get('cpu', {}).get('count', 0),
                memory_total=metrics_data.get('memory', {}).get('total', 0),
                disk_total=metrics_data.get('disk', {}).get('total', 0),
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as e:
            raise ServiceError(
                f"Failed to collect system info: {str(e)}",
                category="system_information",
                severity=ErrorSeverity.MEDIUM
            ) from e

    async def is_healthy(self) -> bool:
        """
        Quick health check.

        Returns:
            True if system is healthy, False otherwise
        """
        try:
            return await self.metrics_facade.is_system_healthy()
        except Exception:
            return False

    async def get_detailed_health_report(self) -> Dict[str, Any]:
        """
        Get detailed health report with recommendations.

        Returns:
            Detailed health report with metrics and recommendations
        """
        try:
            health_metrics = await self.get_health_metrics()
            system_info = await self.get_system_info()
            health_status = await self.metrics_facade.get_health_status()

            return {
                'summary': health_status,
                'metrics': health_metrics.dict(),
                'system_info': system_info.dict(),
                'recommendations': self._generate_recommendations(health_metrics),
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'service_status': 'operational'
            }

        except Exception as e:
            raise ServiceError(
                f"Failed to generate health report: {str(e)}",
                category="health_reporting",
                severity=ErrorSeverity.MEDIUM
            ) from e

    def _extract_cpu_metrics(self, cpu_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize CPU metrics."""
        if cpu_data.get('error'):
            return {'available': False, 'error': cpu_data['error']}

        return {
            'usage_percent': cpu_data.get('usage_percent', 0),
            'load_average': cpu_data.get('load_average', []),
            'core_count': cpu_data.get('count', 0),
            'frequency': cpu_data.get('frequency', 0),
            'available': True
        }

    def _extract_memory_metrics(self, memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize memory metrics."""
        if memory_data.get('error'):
            return {'available': False, 'error': memory_data['error']}

        return {
            'usage_percent': memory_data.get('usage_percent', 0),
            'total_gb': memory_data.get('total', 0) / (1024**3),
            'available_gb': memory_data.get('available', 0) / (1024**3),
            'used_gb': memory_data.get('used', 0) / (1024**3),
            'available': True
        }

    def _extract_disk_metrics(self, disk_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize disk metrics."""
        if disk_data.get('error'):
            return {'available': False, 'error': disk_data['error']}

        return {
            'usage_percent': disk_data.get('usage_percent', 0),
            'total_gb': disk_data.get('total', 0) / (1024**3),
            'free_gb': disk_data.get('free', 0) / (1024**3),
            'used_gb': disk_data.get('used', 0) / (1024**3),
            'available': True
        }

    async def _calculate_overall_health(self, metrics_data: Dict[str, Any]) -> str:
        """Calculate overall system health status."""
        issues = []
        
        # Check CPU health
        cpu = metrics_data.get('cpu', {})
        if not cpu.get('error') and cpu.get('usage_percent', 0) > 90:
            issues.append('high_cpu')

        # Check memory health
        memory = metrics_data.get('memory', {})
        if not memory.get('error') and memory.get('usage_percent', 0) > 85:
            issues.append('high_memory')

        # Check disk health
        disk = metrics_data.get('disk', {})
        if not disk.get('error') and disk.get('usage_percent', 0) > 90:
            issues.append('high_disk')

        # Determine overall status
        if not issues:
            return 'healthy'
        elif len(issues) == 1 and 'high_disk' not in issues:
            return 'warning'
        else:
            return 'critical'

    def _generate_recommendations(self, health_metrics: HealthMetrics) -> list[str]:
        """Generate health recommendations based on metrics."""
        recommendations = []
        
        if hasattr(health_metrics, 'cpu') and health_metrics.cpu.get('usage_percent', 0) > 80:
            recommendations.append("Consider reducing CPU load or scaling resources")
            
        if hasattr(health_metrics, 'memory') and health_metrics.memory.get('usage_percent', 0) > 80:
            recommendations.append("Memory usage is high - consider freeing up memory or adding more RAM")
            
        if hasattr(health_metrics, 'disk') and health_metrics.disk.get('usage_percent', 0) > 85:
            recommendations.append("Disk space is running low - cleanup or expand storage")

        return recommendations

    def _get_platform_info(self) -> Dict[str, Any]:
        """Get platform information."""
        # This would integrate with platform manager
        return {
            'name': 'unknown',
            'version': 'unknown',
            'architecture': 'unknown'
        }

    def _get_system_uptime(self) -> float:
        """Get system uptime in seconds."""
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.readline().split()[0])
        except:
            return 0.0


class HealthServiceRegistry:
    """Registry for managing health service instances."""

    _instance: UnifiedHealthService = None

    @classmethod
    def get_instance(cls, metrics_facade: MetricsFacade = None) -> UnifiedHealthService:
        """Get singleton health service instance."""
        if cls._instance is None:
            if metrics_facade is None:
                raise ValueError("MetricsFacade required for first initialization")
            cls._instance = UnifiedHealthService(metrics_facade)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None