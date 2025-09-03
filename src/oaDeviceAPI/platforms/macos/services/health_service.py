"""
macOS-specific health service implementation.

Provides macOS-specific health monitoring capabilities using system tools
and libraries available on macOS platforms.
"""

from typing import Dict, Any
import asyncio
import subprocess
from datetime import datetime, timezone

from ....core.interfaces import BaseHealthService, MetricsCollectorInterface
from ....core.exceptions import ServiceError, ErrorSeverity
from ....models.health_schemas import HealthMetrics, SystemInfo


class MacOSHealthService(BaseHealthService):
    """macOS-specific implementation of health service."""

    def __init__(self, metrics_collector: MetricsCollectorInterface):
        """
        Initialize macOS health service.

        Args:
            metrics_collector: Platform-specific metrics collector
        """
        self.metrics_collector = metrics_collector

    async def get_health_metrics(self) -> HealthMetrics:
        """
        Get health metrics using macOS-specific data sources.

        Returns:
            HealthMetrics with macOS-specific data
        """
        try:
            # Collect all metrics concurrently
            metrics_data = await self.metrics_collector.collect_all_metrics()

            # Add macOS-specific health data
            macos_specific = await self._get_macos_health_data()
            metrics_data.update(macos_specific)

            return HealthMetrics(
                cpu=metrics_data.get('cpu', {}),
                memory=metrics_data.get('memory', {}),
                disk=metrics_data.get('disk', {}),
                timestamp=datetime.now(timezone.utc),
                platform_specific=macos_specific
            )

        except Exception as e:
            raise ServiceError(
                f"Failed to collect macOS health metrics: {str(e)}",
                category="macos_health",
                severity=ErrorSeverity.HIGH
            ) from e

    async def get_system_info(self) -> SystemInfo:
        """
        Get macOS system information.

        Returns:
            SystemInfo with macOS-specific details
        """
        try:
            # Get basic metrics
            metrics_data = await self.metrics_collector.collect_all_metrics()

            # Get macOS-specific system info
            macos_info = await self._get_macos_system_info()

            return SystemInfo(
                platform="macos",
                platform_version=macos_info.get('version', 'unknown'),
                uptime=macos_info.get('uptime', 0),
                load_average=metrics_data.get('cpu', {}).get('load_average', []),
                cpu_count=metrics_data.get('cpu', {}).get('count', 0),
                memory_total=metrics_data.get('memory', {}).get('total', 0),
                disk_total=metrics_data.get('disk', {}).get('total', 0),
                timestamp=datetime.now(timezone.utc),
                platform_specific=macos_info
            )

        except Exception as e:
            raise ServiceError(
                f"Failed to collect macOS system info: {str(e)}",
                category="macos_system_info",
                severity=ErrorSeverity.MEDIUM
            ) from e

    async def is_healthy(self) -> bool:
        """
        Check if macOS system is healthy.

        Returns:
            True if system is healthy
        """
        try:
            health_metrics = await self.get_health_metrics()
            
            # Check critical macOS-specific health indicators
            cpu_healthy = health_metrics.cpu.get('usage_percent', 0) < 90
            memory_healthy = health_metrics.memory.get('usage_percent', 0) < 85
            disk_healthy = health_metrics.disk.get('usage_percent', 0) < 90

            return cpu_healthy and memory_healthy and disk_healthy

        except Exception:
            return False

    async def _get_macos_health_data(self) -> Dict[str, Any]:
        """Get macOS-specific health data."""
        health_data = {}

        try:
            # Get thermal state
            health_data['thermal'] = await self._get_thermal_state()
            
            # Get power status
            health_data['power'] = await self._get_power_status()
            
            # Get service status for key macOS services
            health_data['services'] = await self._get_service_status()

        except Exception as e:
            health_data['error'] = f"Failed to collect macOS health data: {str(e)}"

        return health_data

    async def _get_macos_system_info(self) -> Dict[str, Any]:
        """Get macOS-specific system information."""
        system_info = {}

        try:
            # Get macOS version
            version_output = await self._run_command(['sw_vers', '-productVersion'])
            system_info['version'] = version_output.strip()

            # Get system uptime
            uptime_output = await self._run_command(['uptime'])
            system_info['uptime_string'] = uptime_output.strip()

            # Get hardware info
            hardware_info = await self._run_command(['system_profiler', 'SPHardwareDataType', '-detailLevel', 'mini'])
            system_info['hardware'] = hardware_info.strip()

        except Exception as e:
            system_info['error'] = f"Failed to collect macOS system info: {str(e)}"

        return system_info

    async def _get_thermal_state(self) -> Dict[str, Any]:
        """Get macOS thermal state."""
        try:
            # Use pmset to check thermal conditions
            output = await self._run_command(['pmset', '-g', 'therm'])
            return {'thermal_state': output.strip(), 'available': True}
        except Exception:
            return {'available': False}

    async def _get_power_status(self) -> Dict[str, Any]:
        """Get macOS power management status."""
        try:
            # Use pmset to check power status
            output = await self._run_command(['pmset', '-g', 'batt'])
            return {'battery_status': output.strip(), 'available': True}
        except Exception:
            return {'available': False}

    async def _get_service_status(self) -> Dict[str, Any]:
        """Get status of key macOS services."""
        services = {}
        key_services = [
            'com.orangead.deviceapi',
            'com.orangead.tracker', 
            'com.orangead.parking-monitor'
        ]

        for service in key_services:
            try:
                # Check launchctl status
                output = await self._run_command(['launchctl', 'list', service])
                services[service] = {
                    'status': 'running' if output.strip() else 'not_found',
                    'available': True
                }
            except Exception:
                services[service] = {'status': 'error', 'available': False}

        return services

    async def _run_command(self, command: list[str], timeout: float = 5.0) -> str:
        """
        Run a system command asynchronously.

        Args:
            command: Command to run as list
            timeout: Command timeout in seconds

        Returns:
            Command output as string

        Raises:
            ServiceError: If command fails
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            if process.returncode != 0:
                raise ServiceError(
                    f"Command {' '.join(command)} failed with return code {process.returncode}: {stderr.decode()}",
                    category="command_execution",
                    severity=ErrorSeverity.MEDIUM
                )

            return stdout.decode()

        except asyncio.TimeoutError:
            raise ServiceError(
                f"Command {' '.join(command)} timed out after {timeout} seconds",
                category="command_timeout",
                severity=ErrorSeverity.MEDIUM
            )
        except Exception as e:
            raise ServiceError(
                f"Failed to execute command {' '.join(command)}: {str(e)}",
                category="command_execution",
                severity=ErrorSeverity.MEDIUM
            ) from e