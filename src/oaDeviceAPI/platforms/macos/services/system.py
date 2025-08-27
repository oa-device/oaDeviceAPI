import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from typing import Dict

import psutil

from ....core.config import LAUNCHCTL_CMD, PS_CMD, TRACKER_ROOT
from .utils import run_command
from .temperature import get_temperature_metrics


def get_system_metrics() -> Dict:
    """Get comprehensive system metrics including CPU, memory, disk, and network usage."""
    try:
        # Get base metrics (keeping existing structure)
        cpu_metrics = {
            "percent": psutil.cpu_percent(interval=1),
            "cores": psutil.cpu_count(),
            "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "per_core": psutil.cpu_percent(interval=1, percpu=True),
        }

        memory = psutil.virtual_memory()
        memory_metrics = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free,
            "cached": getattr(memory, "cached", 0),
            "buffers": getattr(memory, "buffers", 0),
        }

        disk = psutil.disk_usage("/")
        disk_metrics = {
            "total": disk.total,
            "free": disk.free,
            "percent": disk.percent,
            "used": disk.used,
        }

        # Add disk I/O metrics
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                disk_metrics["io"] = {
                    "read_bytes": disk_io.read_bytes,
                    "write_bytes": disk_io.write_bytes,
                    "read_count": disk_io.read_count,
                    "write_count": disk_io.write_count,
                }
        except Exception:
            pass

        # Add network metrics
        try:
            network_metrics = {
                "interfaces": {},
                "connections": len(psutil.net_connections()),
            }

            # Get network interface stats
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters(pernic=True)

            for iface, stats in net_if_stats.items():
                interface_metrics = {
                    "up": stats.isup,
                    "speed": stats.speed,
                    "mtu": stats.mtu,
                }

                # Add IO metrics if available
                if iface in net_io_counters:
                    io_stats = net_io_counters[iface]
                    interface_metrics.update(
                        {
                            "bytes_sent": io_stats.bytes_sent,
                            "bytes_recv": io_stats.bytes_recv,
                            "packets_sent": io_stats.packets_sent,
                            "packets_recv": io_stats.packets_recv,
                            "errors_in": io_stats.errin,
                            "errors_out": io_stats.errout,
                        }
                    )

                network_metrics["interfaces"][iface] = interface_metrics
        except Exception:
            network_metrics = {}

        # Get temperature metrics
        try:
            temperature_metrics = get_temperature_metrics()
        except Exception as e:
            temperature_metrics = {
                "timestamp": datetime.now().isoformat(),
                "thermal_health": "unknown",
                "error": str(e)
            }

        return {
            "cpu": cpu_metrics,
            "memory": memory_metrics,
            "disk": disk_metrics,
            "network": network_metrics,
            "boot_time": psutil.boot_time(),
            "temperature": temperature_metrics,
        }
    except Exception as e:
        return {
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "cores": psutil.cpu_count(),
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total": psutil.disk_usage("/").total,
                "free": psutil.disk_usage("/").free,
                "percent": psutil.disk_usage("/").percent,
            },
            "error": str(e),
        }


def get_service_info(service_name: str) -> Dict:
    """Get detailed information about a launchd service."""
    info = {
        "status": "unknown",
        "pid": "unknown",
        "activestate": "unknown",
        "substate": "unknown",
    }

    try:
        # Check if service is running using launchctl
        cmd = [LAUNCHCTL_CMD, "list"]
        output = run_command(cmd)

        # Parse the output to find the service
        for line in output.split("\n"):
            if service_name in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[0]
                    if pid != "-":
                        info["pid"] = pid
                        info["status"] = "active"
                        info["activestate"] = "active"
                        info["substate"] = "running"
                    else:
                        info["status"] = "inactive"
                        info["activestate"] = "inactive"
                        info["substate"] = "dead"
                    break

        # If service wasn't found in the list, it's not loaded
        if info["status"] == "unknown":
            info["status"] = "inactive"
            info["activestate"] = "inactive"
            info["substate"] = "dead"

    except Exception:
        pass

    return info


def get_device_info() -> Dict[str, str]:
    """Get device type and series based on hostname and check if headless."""
    hostname = platform.node().lower()

    # Extract series and number from hostname (e.g., 'mac0001', 'labatt0002')
    series_match = re.match(r"^([a-z]+)(\d+)$", hostname)
    series = series_match.group(1).upper() if series_match else "UNKNOWN"

    # Check if the system has a display
    is_headless = False
    try:
        # Try to get display info using system_profiler
        display_cmd = ["system_profiler", "SPDisplaysDataType"]
        display_output = run_command(display_cmd)

        # If no displays are found or output is empty, consider it headless
        if not display_output or "No Display Found" in display_output:
            is_headless = True
    except Exception:
        # If command fails, assume it might be headless
        is_headless = True

    return {
        "type": "Mac",
        "series": series,
        "hostname": hostname,
        "is_headless": is_headless,
    }


def get_version_info() -> Dict:
    """Get system and tracker version information."""
    try:
        # Get system info using platform module
        system_info = {
            "os": platform.system(),
            "platform": "macOS",  # Explicitly set platform for clarity
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        }

        # Get macOS version using platform.mac_ver() - more reliable than parsing sw_vers
        mac_ver = platform.mac_ver()
        if mac_ver and mac_ver[0]:
            system_info["macos_version"] = mac_ver[
                0
            ]  # Release version (e.g., "13.4.1")
            if mac_ver[2]:
                system_info["machine_type"] = mac_ver[
                    2
                ]  # Machine type (e.g., "x86_64" or "arm64")

        # Get additional version details using sw_vers for completeness
        try:
            product_name = run_command(["sw_vers", "-productName"]).strip()
            product_version = run_command(["sw_vers", "-productVersion"]).strip()
            build_version = run_command(["sw_vers", "-buildVersion"]).strip()

            if product_name:
                system_info["product_name"] = product_name  # Usually "macOS"
            if product_version:
                system_info["macos_version"] = (
                    product_version  # Ensure we have this even if mac_ver failed
                )
            if build_version:
                system_info["build_version"] = (
                    build_version  # Build number (e.g., "22F82")
                )
        except Exception as e:
            system_info["sw_vers_error"] = str(e)

        # Calculate uptime from boot_time
        try:
            boot_timestamp = psutil.boot_time()
            current_timestamp = datetime.now(timezone.utc).timestamp()
            uptime_seconds = int(current_timestamp - boot_timestamp)

            # Format uptime in a human-readable format
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)

            system_info["uptime"] = {
                "seconds": uptime_seconds,
                "formatted": f"{days}d {hours}h {minutes}m {seconds}s",
                "boot_time": datetime.fromtimestamp(
                    boot_timestamp, timezone.utc
                ).isoformat(),
            }
        except Exception as e:
            system_info["uptime_error"] = str(e)

        # Extract series from hostname (e.g., mac0001 -> MAC)
        hostname = system_info["hostname"].lower()
        series_match = re.match(r"^([a-zA-Z]+)", hostname)
        if series_match:
            system_info["series"] = series_match.group(
                1
            ).upper()  # Standardize to uppercase
            system_info["device_id"] = hostname  # Include full device ID

        # Get tracker version if available
        tracker_version_file = TRACKER_ROOT / "version.txt"
        if tracker_version_file.exists():
            with open(tracker_version_file) as f:
                system_info["tracker_version"] = f.read().strip()

        # Get Tailscale version
        try:
            # Check both possible locations for Tailscale
            tailscale_paths = [
                "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                "/usr/local/bin/tailscale",
            ]

            for path in tailscale_paths:
                if os.path.exists(path):
                    tailscale_version_output = run_command([path, "version"]).strip()
                    if tailscale_version_output:
                        # Extract just the version number from the first line
                        version_number = tailscale_version_output.split("\n")[0].strip()
                        system_info["tailscale_version"] = version_number
                        break

            if "tailscale_version" not in system_info:
                system_info["tailscale_version"] = None
        except Exception as e:
            system_info["tailscale_error"] = str(e)

        return system_info
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}
