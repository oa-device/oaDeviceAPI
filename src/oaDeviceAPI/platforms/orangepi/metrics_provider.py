"""
OrangePi-specific metrics provider for the unified metrics system.

This module provides OrangePi-specific implementations for metrics collection,
integrating with existing OrangePi services while conforming to the unified interface.
"""

import re
from datetime import UTC
from pathlib import Path
from typing import Any

from ...core.metrics import PlatformMetricsProvider
from ...core.utils import run_command


class OrangePiMetricsProvider(PlatformMetricsProvider):
    """OrangePi-specific implementation of the metrics provider protocol."""

    def get_version_info(self) -> dict[str, Any]:
        """Get OrangePi-specific version information."""
        try:
            import platform

            version_info = {
                "os": platform.system(),
                "platform": "OrangePi",
                "machine": platform.machine(),
                "processor": platform.processor() or "ARM Cortex",
                "hostname": platform.node(),
            }

            # Get kernel version
            try:
                kernel_version = run_command(["uname", "-r"]).strip()
                if kernel_version:
                    version_info["kernel_version"] = kernel_version
            except Exception:
                pass

            # Get distribution information
            try:
                if Path("/etc/os-release").exists():
                    with open("/etc/os-release") as f:
                        os_release = f.read()

                    # Parse os-release file
                    for line in os_release.split('\n'):
                        if line.startswith('NAME='):
                            version_info["distribution_name"] = line.split('=', 1)[1].strip('"')
                        elif line.startswith('VERSION='):
                            version_info["distribution_version"] = line.split('=', 1)[1].strip('"')
                        elif line.startswith('VERSION_ID='):
                            version_info["distribution_version_id"] = line.split('=', 1)[1].strip('"')
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

            # Get OrangePi model information
            try:
                if Path("/proc/device-tree/model").exists():
                    with open("/proc/device-tree/model") as f:
                        model = f.read().strip().replace('\x00', '')
                        version_info["board_model"] = model
            except Exception:
                pass

            return version_info

        except Exception:
            return {
                "platform": "OrangePi",
                "error": "Failed to collect version information"
            }

    def get_device_info(self) -> dict[str, Any]:
        """Get OrangePi-specific device information."""
        try:
            import platform

            hostname = platform.node().lower()

            # Extract series and number from hostname
            series_match = re.match(r"^([a-z]+)(\d+)$", hostname)
            series = series_match.group(1).upper() if series_match else "ORANGEPI"

            # Get model from device tree
            model = "OrangePi"
            try:
                if Path("/proc/device-tree/model").exists():
                    with open("/proc/device-tree/model") as f:
                        model = f.read().strip().replace('\x00', '')
            except Exception:
                pass

            # Check display connection
            display_connected = False
            try:
                # Check for display configuration or active display
                display_output = run_command(["xrandr", "--listmonitors"])
                if display_output and "Monitors:" in display_output:
                    # Parse monitor count
                    monitor_line = [line for line in display_output.split('\n')
                                  if line.startswith('Monitors:')]
                    if monitor_line:
                        monitor_count = int(monitor_line[0].split()[1])
                        display_connected = monitor_count > 0
            except Exception:
                # Alternative check using /sys/class/drm
                try:
                    drm_path = Path("/sys/class/drm")
                    if drm_path.exists():
                        for card_path in drm_path.glob("card*"):
                            status_file = card_path / "status"
                            if status_file.exists():
                                with open(status_file) as f:
                                    status = f.read().strip()
                                    if status == "connected":
                                        display_connected = True
                                        break
                except Exception:
                    pass

            return {
                "type": "OrangePi",
                "series": series,
                "hostname": hostname,
                "model": model,
                "display_connected": display_connected,
            }

        except Exception:
            return {
                "type": "OrangePi",
                "series": "ORANGEPI",
                "hostname": "unknown",
                "model": "OrangePi",
                "display_connected": False,
            }

    def get_additional_cpu_info(self) -> dict[str, Any]:
        """Get additional OrangePi-specific CPU information."""
        try:
            cpu_info = {}

            # Read CPU info from /proc/cpuinfo
            try:
                with open("/proc/cpuinfo") as f:
                    cpuinfo = f.read()

                for line in cpuinfo.split('\n'):
                    if line.startswith('model name'):
                        cpu_info["model"] = line.split(':', 1)[1].strip()
                        break
                    elif line.startswith('Hardware'):
                        cpu_info["hardware"] = line.split(':', 1)[1].strip()
                    elif line.startswith('Revision'):
                        cpu_info["revision"] = line.split(':', 1)[1].strip()
            except Exception:
                pass

            # Fallback model if not found
            if "model" not in cpu_info:
                cpu_info["model"] = "ARM Cortex"

            # Get CPU frequency information
            try:
                # Current frequency
                freq_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
                if freq_path.exists():
                    with open(freq_path) as f:
                        current_freq = int(f.read().strip()) // 1000  # Convert to MHz
                        cpu_info["current_frequency_mhz"] = current_freq

                # Max frequency
                max_freq_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
                if max_freq_path.exists():
                    with open(max_freq_path) as f:
                        max_freq = int(f.read().strip()) // 1000  # Convert to MHz
                        cpu_info["max_frequency_mhz"] = max_freq
            except Exception:
                pass

            return cpu_info

        except Exception:
            return {"model": "ARM Cortex"}

    def get_additional_system_info(self) -> dict[str, Any]:
        """Get additional OrangePi-specific system information."""
        try:
            additional_info = {}

            # Get memory information from /proc/meminfo
            try:
                with open("/proc/meminfo") as f:
                    meminfo = f.read()

                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        total_kb = int(line.split()[1])
                        additional_info["total_memory"] = f"{total_kb // 1024} MB"
                        break
            except Exception:
                pass

            # Get temperature information if available
            try:
                temp_paths = [
                    "/sys/class/thermal/thermal_zone0/temp",
                    "/sys/class/hwmon/hwmon0/temp1_input"
                ]

                for temp_path in temp_paths:
                    if Path(temp_path).exists():
                        with open(temp_path) as f:
                            temp_raw = int(f.read().strip())
                            # Temperature is usually in millidegrees
                            temp_celsius = temp_raw / 1000 if temp_raw > 1000 else temp_raw
                            additional_info["cpu_temperature"] = f"{temp_celsius:.1f}°C"
                            break
            except Exception:
                pass

            # Get GPIO information
            try:
                gpio_path = Path("/sys/class/gpio")
                if gpio_path.exists():
                    gpio_chips = list(gpio_path.glob("gpiochip*"))
                    additional_info["gpio_chips"] = len(gpio_chips)
            except Exception:
                pass

            # Check for display manager
            try:
                display_manager = run_command(["systemctl", "is-active", "lightdm"])
                if display_manager.strip() == "active":
                    additional_info["display_manager"] = "lightdm"
            except Exception:
                pass

            return additional_info

        except Exception:
            return {}

    def get_platform_capabilities(self) -> dict[str, Any]:
        """Get OrangePi-specific platform capabilities."""
        capabilities = {
            "screenshot_supported": True,
            "camera_supported": False,  # Typically no built-in camera support
            "tracker_supported": False,  # No AI tracking on OrangePi
            "camguard_supported": False,
            "display_management": True,
            "service_management": "systemctl",
            "player_supported": True,
            "gpio_supported": True,
            "temperature_monitoring": True,
        }

        # Check for specific capabilities
        try:
            # Check if GPIO is available
            gpio_path = Path("/sys/class/gpio")
            capabilities["gpio_available"] = gpio_path.exists()

            # Check if display server is running
            try:
                display_check = run_command(["pgrep", "Xorg"])
                capabilities["x11_running"] = bool(display_check.strip())
            except Exception:
                capabilities["x11_running"] = False

            # Check for camera devices (USB cameras)
            video_devices = list(Path("/dev").glob("video*"))
            capabilities["usb_camera_devices"] = len(video_devices)

            # Check systemd status
            try:
                systemd_check = run_command(["systemctl", "--version"])
                capabilities["systemd_available"] = "systemd" in systemd_check
            except Exception:
                capabilities["systemd_available"] = False

        except Exception:
            pass

        return capabilities
