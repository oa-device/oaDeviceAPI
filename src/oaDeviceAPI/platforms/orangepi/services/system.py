import os
import platform
from pathlib import Path

import psutil

from ....core.config import settings
from ....core.utils import run_command

# Constants with fallbacks
SYSTEMCTL_CMD = getattr(settings, 'systemctl_cmd', 'systemctl')
PS_CMD = getattr(settings, 'ps_cmd', 'ps')
PLAYER_ROOT = getattr(settings, 'player_root', '/home/orangepi/Orangead/player')


def get_system_metrics() -> dict:
    """Get comprehensive system metrics including CPU, memory, disk, and network usage."""
    try:
        # Get base metrics (keeping existing structure)
        cpu_metrics = {
            "percent": psutil.cpu_percent(interval=1),
            "cores": psutil.cpu_count(),
            "cores_logical": psutil.cpu_count(logical=True),
            "core_usage": psutil.cpu_percent(interval=1, percpu=True),
        }

        # Memory metrics
        memory = psutil.virtual_memory()
        memory_metrics = {
            "percent": memory.percent,
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
        }

        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_metrics = {
            "percent": (disk.used / disk.total) * 100,
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
        }

        # Network metrics
        net_io = psutil.net_io_counters()
        network_metrics = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }

        # System uptime
        uptime_seconds = psutil.boot_time()

        return {
            "cpu": cpu_metrics,
            "memory": memory_metrics,
            "disk": disk_metrics,
            "network": network_metrics,
            "uptime_seconds": uptime_seconds,
            "hostname": platform.node(),
            "platform": platform.platform(),
        }
    except Exception as e:
        return {"error": str(e)}


def get_device_info() -> dict:
    """Get device-specific information."""
    try:
        # Get basic system information
        info = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "architecture": platform.architecture(),
            "processor": platform.processor(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "is_headless": check_if_headless(),
        }

        # Add OrangePi specific information
        if Path("/proc/device-tree/model").exists():
            try:
                with open("/proc/device-tree/model") as f:
                    info["device_model"] = f.read().strip()
            except Exception:
                pass

        # Get temperature information if available
        try:
            temp_info = get_temperature_info()
            if temp_info:
                info["temperature"] = temp_info
        except Exception:
            pass

        return info
    except Exception as e:
        return {"error": str(e)}


def get_version_info() -> dict:
    """Get system and player version information."""
    try:
        # Get basic system information
        system_info = {
            "os": platform.system(),
            "platform": "OrangePi",  # Explicitly set platform for clarity
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        }

        # Get Linux distribution information
        try:
            if Path("/etc/os-release").exists():
                with open("/etc/os-release") as f:
                    os_release = f.read()
                    for line in os_release.split('\n'):
                        if line.startswith('PRETTY_NAME='):
                            system_info["distribution"] = line.split('=', 1)[1].strip('"')
                            break
                        elif line.startswith('NAME='):
                            system_info["distribution"] = line.split('=', 1)[1].strip('"')
        except Exception:
            pass

        # Get kernel version
        try:
            kernel_version = platform.release()
            if kernel_version:
                system_info["kernel_version"] = kernel_version
        except Exception:
            pass

        # Get device model information
        try:
            if Path("/proc/device-tree/model").exists():
                with open("/proc/device-tree/model") as f:
                    device_model = f.read().strip()
                    if device_model:
                        system_info["device_model"] = device_model
        except Exception:
            pass

        # Get player version if available
        try:
            version_file = Path(PLAYER_ROOT) / "version.txt"
            if version_file.exists():
                player_version = version_file.read_text().strip()
                system_info["player_version"] = player_version
        except Exception:
            pass

        return system_info
    except Exception as e:
        return {"error": str(e)}


def check_if_headless() -> bool:
    """Check if the system is running headless (no display)."""
    try:
        display_env = os.environ.get("DISPLAY", "")
        if not display_env:
            return True

        # Check if there are any connected displays
        result = run_command(["xrandr", "--query"])
        if result:
            lines = result.split("\n")
            for line in lines:
                if " connected " in line:
                    return False

        return True
    except Exception:
        return True  # Assume headless if we can't determine


def get_temperature_info() -> dict | None:
    """Get temperature information if available."""
    try:
        temperatures = {}

        # Check for thermal zone information
        thermal_zone_path = Path("/sys/class/thermal")
        if thermal_zone_path.exists():
            for zone_dir in thermal_zone_path.glob("thermal_zone*"):
                try:
                    temp_file = zone_dir / "temp"
                    type_file = zone_dir / "type"

                    if temp_file.exists() and type_file.exists():
                        temp_raw = int(temp_file.read_text().strip())
                        temp_celsius = temp_raw / 1000.0  # Convert millicelsius to celsius
                        zone_type = type_file.read_text().strip()

                        temperatures[zone_type] = {
                            "celsius": temp_celsius,
                            "fahrenheit": (temp_celsius * 9/5) + 32
                        }
                except Exception:
                    continue

        return temperatures if temperatures else None
    except Exception:
        return None


def get_service_info(service_name: str) -> dict:
    """Get information about a systemd service."""
    try:
        # Get service status using systemctl
        status_result = run_command([SYSTEMCTL_CMD, "is-active", service_name])
        enabled_result = run_command([SYSTEMCTL_CMD, "is-enabled", service_name])

        # Get detailed status
        show_result = run_command([SYSTEMCTL_CMD, "show", service_name, "--property=ActiveState,SubState,LoadState,UnitFileState"])

        service_info = {
            "name": service_name,
            "active": status_result == "active",
            "enabled": enabled_result == "enabled",
            "status": status_result,
            "enabled_status": enabled_result,
        }

        # Parse detailed status
        if show_result:
            for line in show_result.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key == "ActiveState":
                        service_info["active_state"] = value
                    elif key == "SubState":
                        service_info["sub_state"] = value
                    elif key == "LoadState":
                        service_info["load_state"] = value
                    elif key == "UnitFileState":
                        service_info["unit_file_state"] = value

        return service_info
    except Exception as e:
        return {
            "name": service_name,
            "error": str(e),
            "active": False,
            "enabled": False,
        }
