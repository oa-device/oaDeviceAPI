"""Real temperature monitoring service for macOS devices using SMC."""

import os
import subprocess
from datetime import datetime

from .utils import run_command


def get_cpu_temperature() -> float | None:
    """Get real CPU temperature using smctemp binary via Apple SMC."""
    try:
        # Path to smctemp binary (integrated into oaDeviceAPI)
        smctemp_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "bin", "macos", "smctemp")

        # Fallback paths if not found in expected location
        fallback_paths = [
            "/usr/local/bin/smctemp",
            os.path.expanduser("~/orangead/macos-api/macos_api/bin/smctemp"),
            "smctemp"  # If it's in PATH
        ]

        # Find available smctemp binary
        binary_path = None
        if os.path.exists(smctemp_path) and os.access(smctemp_path, os.X_OK):
            binary_path = smctemp_path
        else:
            for path in fallback_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    binary_path = path
                    break

        if not binary_path:
            # No fallback - return None if smctemp not available
            return None

        # Run smctemp to get real temperature
        # Try different temperature sensors for M1/M2 Macs (prioritize CPU core temperatures)
        temp_sensors = ["Te05", "Te06", "Ts0C", "Ts0D", "-c"]

        for sensor in temp_sensors:
            try:
                if sensor == "-c":
                    output = run_command([binary_path, "-c"])
                else:
                    # For specific sensors, use the full sensor list and parse
                    output = run_command([binary_path, "-l"])
                    for line in output.split('\n'):
                        if line.strip().startswith(sensor):
                            # Parse temperature from line like "Te05  +45.6°C  (ht06)"
                            parts = line.split()
                            if len(parts) >= 2:
                                temp_str = parts[1].replace('+', '').replace('°C', '')
                                return float(temp_str)
                            break
                    continue

                # Parse output for -c flag (CPU temperature)
                if output and output != "":
                    # Output like "+45.6°C" or just "45.6"
                    temp_str = output.replace('+', '').replace('°C', '').strip()
                    if temp_str:
                        return float(temp_str)
            except (ValueError, subprocess.TimeoutExpired):
                continue

        return None

    except Exception:
        return None


def get_all_temperatures() -> dict[str, float]:
    """Get all available temperature sensors from SMC."""
    temperatures = {}

    try:
        # Path to smctemp binary
        smctemp_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "bin", "macos", "smctemp")

        # Fallback paths if not found in expected location
        fallback_paths = [
            "/usr/local/bin/smctemp",
            os.path.expanduser("~/orangead/macos-api/macos_api/bin/smctemp"),
            "smctemp"  # If it's in PATH
        ]

        # Find available smctemp binary
        binary_path = None
        if os.path.exists(smctemp_path) and os.access(smctemp_path, os.X_OK):
            binary_path = smctemp_path
        else:
            for path in fallback_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    binary_path = path
                    break

        if not binary_path:
            return temperatures

        # Get all temperature sensors
        output = run_command([binary_path, "-l"])

        for line in output.split('\n'):
            if line.strip() and "°C" in line:
                parts = line.split()
                if len(parts) >= 2:
                    sensor_name = parts[0]
                    temp_str = parts[1].replace('+', '').replace('°C', '')
                    try:
                        temperatures[sensor_name] = float(temp_str)
                    except ValueError:
                        continue

    except Exception:
        pass

    return temperatures


def get_temperature_metrics() -> dict:
    """Get comprehensive temperature metrics for macOS devices."""
    try:
        # Get CPU temperature
        cpu_temp = get_cpu_temperature()

        # Get all available temperatures
        all_temps = get_all_temperatures()

        # Calculate statistics if we have temperature data
        temp_values = list(all_temps.values()) if all_temps else []

        return {
            "cpu": {
                "celsius": cpu_temp,
                "fahrenheit": (cpu_temp * 9/5 + 32) if cpu_temp else None,
                "status": "normal" if cpu_temp and cpu_temp < 70 else "warm" if cpu_temp and cpu_temp < 85 else "hot" if cpu_temp else "unknown"
            },
            "sensors": all_temps,
            "statistics": {
                "count": len(temp_values),
                "average": sum(temp_values) / len(temp_values) if temp_values else None,
                "min": min(temp_values) if temp_values else None,
                "max": max(temp_values) if temp_values else None,
                "hot_count": len([t for t in temp_values if t > 70]) if temp_values else 0
            },
            "thermal_state": {
                "pressure": get_thermal_pressure(),
                "speed_limit": get_speed_limit_status()
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "error": str(e),
            "cpu": {"celsius": None, "fahrenheit": None, "status": "error"},
            "sensors": {},
            "statistics": {"count": 0},
            "thermal_state": {"pressure": "unknown", "speed_limit": "unknown"},
            "timestamp": datetime.now().isoformat()
        }


def get_thermal_pressure() -> str:
    """Get thermal pressure state from macOS."""
    try:
        # Try to get thermal pressure info using pmset
        output = run_command(["pmset", "-g", "therm"])
        if "thermal pressure" in output.lower():
            if "nominal" in output.lower():
                return "nominal"
            elif "moderate" in output.lower():
                return "moderate"
            elif "heavy" in output.lower():
                return "heavy"
            elif "trapping" in output.lower():
                return "critical"
        return "unknown"
    except Exception:
        return "unknown"


def get_speed_limit_status() -> str:
    """Get CPU speed limit status."""
    try:
        # Check if CPU is being throttled
        output = run_command(["pmset", "-g", "therm"])
        if "speed limit" in output.lower():
            if "100%" in output:
                return "normal"
            else:
                # Extract percentage if available
                import re
                match = re.search(r'speed limit (\d+)%', output.lower())
                if match:
                    return f"throttled_{match.group(1)}%"
                return "throttled"
        return "normal"
    except Exception:
        return "unknown"
