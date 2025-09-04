"""
macOS-specific metrics provider for the unified metrics system.

This module provides macOS-specific implementations for metrics collection,
integrating with existing macOS services while conforming to the unified interface.
"""

import re
from datetime import UTC
from pathlib import Path
from typing import Any

from ...core.config import TRACKER_ROOT
from ...core.metrics import PlatformMetricsProvider
from .services.utils import get_system_profiler_info, run_command


class MacOSMetricsProvider(PlatformMetricsProvider):
    """macOS-specific implementation of the metrics provider protocol."""

    def get_version_info(self) -> dict[str, Any]:
        """Get macOS-specific version information."""
        try:
            import platform

            version_info = {
                "os": platform.system(),
                "platform": "macOS",
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
            }

            # Get macOS version using platform.mac_ver() - more reliable
            mac_ver = platform.mac_ver()
            if mac_ver and mac_ver[0]:
                version_info["macos_version"] = mac_ver[0]
                if mac_ver[2]:
                    version_info["machine_type"] = mac_ver[2]

            # Get additional version details using sw_vers
            try:
                product_name = run_command(["sw_vers", "-productName"]).strip()
                product_version = run_command(["sw_vers", "-productVersion"]).strip()
                build_version = run_command(["sw_vers", "-buildVersion"]).strip()

                if product_name:
                    version_info["product_name"] = product_name
                if product_version:
                    version_info["macos_version"] = product_version
                if build_version:
                    version_info["build_version"] = build_version
            except Exception:
                pass

            # Calculate uptime
            try:
                from datetime import datetime

                import psutil

                boot_timestamp = psutil.boot_time()
                current_timestamp = datetime.now(UTC).timestamp()
                uptime_seconds = int(current_timestamp - boot_timestamp)

                days, remainder = divmod(uptime_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)

                version_info["uptime"] = {
                    "seconds": uptime_seconds,
                    "formatted": f"{days}d {hours}h {minutes}m {seconds}s",
                    "boot_time": datetime.fromtimestamp(
                        boot_timestamp, UTC
                    ).isoformat(),
                }
            except Exception:
                pass

            # Get tracker version if available
            tracker_version_file = TRACKER_ROOT / "version.txt"
            if tracker_version_file.exists():
                try:
                    with open(tracker_version_file) as f:
                        version_info["tracker_version"] = f.read().strip()
                except Exception:
                    pass

            # Get Tailscale version
            try:
                tailscale_paths = [
                    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                    "/usr/local/bin/tailscale",
                ]

                for path in tailscale_paths:
                    if Path(path).exists():
                        tailscale_version = run_command([path, "version"]).strip()
                        if tailscale_version:
                            version_info["tailscale_version"] = tailscale_version.split("\n")[0].strip()
                            break

                if "tailscale_version" not in version_info:
                    version_info["tailscale_version"] = None
            except Exception:
                pass

            return version_info

        except Exception:
            return {
                "platform": "macOS",
                "error": "Failed to collect version information"
            }

    def get_device_info(self) -> dict[str, Any]:
        """Get macOS-specific device information."""
        try:
            import platform

            hostname = platform.node().lower()

            # Extract series and number from hostname
            series_match = re.match(r"^([a-z]+)(\d+)$", hostname)
            series = series_match.group(1).upper() if series_match else "UNKNOWN"

            # Check if the system has a display (headless detection)
            is_headless = False
            try:
                display_output = run_command(["system_profiler", "SPDisplaysDataType"])
                if not display_output or "No Display Found" in display_output:
                    is_headless = True
            except Exception:
                is_headless = True

            # Get hardware info from system profiler
            hardware_info = get_system_profiler_info("SPHardwareDataType")
            model_identifier = "Unknown"

            if hardware_info and "SPHardwareDataType" in hardware_info:
                hw_data = hardware_info["SPHardwareDataType"]
                if hw_data and len(hw_data) > 0:
                    model_identifier = hw_data[0].get("machine_model", "Unknown")

            return {
                "type": "Mac",
                "series": series,
                "hostname": hostname,
                "model": model_identifier,
                "is_headless": is_headless,
            }

        except Exception:
            return {
                "type": "Mac",
                "series": "UNKNOWN",
                "hostname": "unknown",
                "model": "Unknown",
                "is_headless": False,
            }

    def get_additional_cpu_info(self) -> dict[str, Any]:
        """Get additional macOS-specific CPU information."""
        try:
            version_info = self.get_version_info()
            cpu_model = version_info.get("processor", "")

            # Try to get more detailed CPU info from system profiler
            hardware_info = get_system_profiler_info("SPHardwareDataType")

            if hardware_info and "SPHardwareDataType" in hardware_info:
                hw_data = hardware_info["SPHardwareDataType"]
                if hw_data and len(hw_data) > 0:
                    hw_item = hw_data[0]
                    cpu_model = hw_item.get("cpu_type", cpu_model)

                    return {
                        "model": cpu_model,
                        "cpu_type": hw_item.get("cpu_type"),
                        "number_processors": hw_item.get("number_processors"),
                        "packages": hw_item.get("packages"),
                    }

            return {"model": cpu_model} if cpu_model else {}

        except Exception:
            return {}

    def get_additional_system_info(self) -> dict[str, Any]:
        """Get additional macOS-specific system information."""
        try:
            additional_info = {}

            # Get hardware info
            hardware_info = get_system_profiler_info("SPHardwareDataType")

            if hardware_info and "SPHardwareDataType" in hardware_info:
                hw_data = hardware_info["SPHardwareDataType"]
                if hw_data and len(hw_data) > 0:
                    hw_item = hw_data[0]
                    additional_info.update({
                        "total_memory": hw_item.get("physical_memory"),
                        "serial_number": hw_item.get("serial_number"),
                        "hardware_uuid": hw_item.get("platform_UUID"),
                        "provisioning_udid": hw_item.get("provisioning_UDID"),
                    })

            # Get software info
            try:
                kernel_version = run_command(["uname", "-v"]).strip()
                if kernel_version:
                    additional_info["kernel_version"] = kernel_version
            except Exception:
                pass

            return additional_info

        except Exception:
            return {}

    def get_platform_capabilities(self) -> dict[str, Any]:
        """Get macOS-specific platform capabilities."""
        return {
            "screenshot_supported": False,
            "camera_supported": True,
            "tracker_supported": True,
            "camguard_supported": True,
            "display_management": True,
            "service_management": "launchctl",
            "temperature_monitoring": True,
            "system_profiler": True,
            "homebrew_supported": Path("/opt/homebrew").exists() or Path("/usr/local/Homebrew").exists(),
            "tailscale_supported": any(
                Path(p).exists() for p in [
                    "/Applications/Tailscale.app",
                    "/usr/local/bin/tailscale"
                ]
            )
        }
