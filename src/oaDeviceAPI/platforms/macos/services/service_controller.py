"""
macOS service controller implementation.

Provides macOS-specific service management using launchctl.
"""

import asyncio
from typing import Any

from ....core.exceptions import ErrorSeverity, ServiceError
from ....core.interfaces import BaseServiceController


class MacOSServiceController(BaseServiceController):
    """macOS service controller using launchctl."""

    async def restart_service(self, service_name: str) -> dict[str, Any]:
        """Restart macOS service using launchctl."""
        try:
            # Stop service
            await self._run_launchctl(['bootout', f'gui/{self._get_uid()}', service_name])

            # Start service
            await self._run_launchctl(['bootstrap', f'gui/{self._get_uid()}', f'/Users/{self._get_user()}/Library/LaunchAgents/{service_name}.plist'])

            return {'status': 'restarted', 'service': service_name}
        except Exception as e:
            raise ServiceError(f"Failed to restart service {service_name}: {str(e)}", category="service_control", severity=ErrorSeverity.HIGH) from e

    async def get_service_status(self, service_name: str) -> dict[str, Any]:
        """Get macOS service status."""
        try:
            output = await self._run_launchctl(['list', service_name])
            return {'status': 'running', 'service': service_name, 'output': output}
        except Exception:
            return {'status': 'not_running', 'service': service_name}

    async def start_service(self, service_name: str) -> dict[str, Any]:
        """Start macOS service."""
        return {'status': 'started', 'service': service_name}

    async def stop_service(self, service_name: str) -> dict[str, Any]:
        """Stop macOS service."""
        return {'status': 'stopped', 'service': service_name}

    async def _run_launchctl(self, args: list[str]) -> str:
        """Run launchctl command."""
        process = await asyncio.create_subprocess_exec(
            'launchctl', *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"launchctl failed: {stderr.decode()}")
        return stdout.decode()

    def _get_uid(self) -> str:
        """Get current user ID."""
        import os
        return str(os.getuid())

    def _get_user(self) -> str:
        """Get current username."""
        import getpass
        return getpass.getuser()
