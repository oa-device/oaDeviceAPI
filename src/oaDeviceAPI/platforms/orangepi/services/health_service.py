"""OrangePi health service implementation."""

from datetime import UTC, datetime

from ....core.interfaces import BaseHealthService, MetricsCollectorInterface
from ....models.health_schemas import HealthMetrics, SystemInfo


class OrangePiHealthService(BaseHealthService):
    """OrangePi-specific health service."""

    def __init__(self, metrics_collector: MetricsCollectorInterface):
        self.metrics_collector = metrics_collector

    async def get_health_metrics(self) -> HealthMetrics:
        """Get OrangePi health metrics."""
        metrics_data = await self.metrics_collector.collect_all_metrics()
        return HealthMetrics(
            cpu=metrics_data.get('cpu', {}),
            memory=metrics_data.get('memory', {}),
            disk=metrics_data.get('disk', {}),
            timestamp=datetime.now(UTC)
        )

    async def get_system_info(self) -> SystemInfo:
        """Get OrangePi system information."""
        metrics_data = await self.metrics_collector.collect_all_metrics()
        return SystemInfo(
            platform="orangepi",
            uptime=0,
            load_average=[],
            cpu_count=metrics_data.get('cpu', {}).get('count', 0),
            memory_total=metrics_data.get('memory', {}).get('total', 0),
            disk_total=metrics_data.get('disk', {}).get('total', 0),
            timestamp=datetime.now(UTC)
        )
