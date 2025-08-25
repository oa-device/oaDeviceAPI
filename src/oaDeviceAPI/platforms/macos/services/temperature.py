"""Real temperature monitoring service for macOS devices using SMC."""

import os
import psutil
from datetime import datetime
from typing import Dict, List, Optional

from .utils import run_command


def get_cpu_temperature() -> Optional[float]:
    """Get real CPU temperature using smctemp binary via Apple SMC."""
    try:
        # Path to smctemp binary (integrated into macos-api)
        smctemp_path = os.path.join(os.path.dirname(__file__), "..", "bin", "smctemp")
        
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
                            # Extract temperature from line like "  Te05  [flt ]  42.3 (bytes: 35 03 29 42)"
                            parts = line.split(']')
                            if len(parts) > 1:
                                temp_part = parts[1].strip().split('(')[0].strip()
                                try:
                                    temp = float(temp_part)
                                    if 0 <= temp <= 120:  # Reasonable temperature range
                                        return round(temp, 1)
                                except ValueError:
                                    continue
                            break
                    continue
                
                temp_str = output.strip()
                
                # Parse temperature value (should be a float like "64.2")
                if temp_str and temp_str.replace('.', '').replace('-', '').isdigit():
                    temp = float(temp_str)
                    if 0 <= temp <= 120:  # Reasonable temperature range
                        return round(temp, 1)
                        
            except Exception as e:
                print(f"Error reading sensor {sensor}: {e}")
                continue
        
        # Return None if real temperature reading fails
        return None
        
    except Exception as e:
        print(f"Error getting real CPU temperature: {e}")
        # Return None if SMC reading fails
        return None




def get_thermal_state() -> Dict[str, any]:
    """Get thermal state information using pmset command."""
    try:
        cmd = ["pmset", "-g", "therm"]
        output = run_command(cmd)
        
        thermal_info = {
            "thermal_state": "normal",
            "cpu_speed_limit": None,
            "thermal_pressure": False
        }
        
        # Parse thermal state output
        for line in output.split('\n'):
            line = line.strip().lower()
            if 'cpu speed limit:' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    try:
                        limit_str = parts[1].strip().replace('%', '')
                        thermal_info["cpu_speed_limit"] = int(limit_str)
                        thermal_info["thermal_pressure"] = int(limit_str) < 100
                    except ValueError:
                        pass
            elif 'thermal state:' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    thermal_info["thermal_state"] = parts[1].strip()
        
        return thermal_info
    except Exception:
        return {
            "thermal_state": "unknown",
            "cpu_speed_limit": None,
            "thermal_pressure": False
        }


def get_temperature_metrics() -> Dict[str, any]:
    """Get real temperature metrics for the macOS device using SMC."""
    timestamp = datetime.now().isoformat()
    
    # Get CPU temperature (real via SMC, fallback to estimation)
    cpu_temp = get_cpu_temperature()
    
    # Get thermal state
    thermal_state = get_thermal_state()
    
    # Determine if we're using real SMC data
    method = "none"
    smctemp_path = os.path.join(os.path.dirname(__file__), "..", "bin", "smctemp")
    fallback_paths = [
        "/usr/local/bin/smctemp",
        os.path.expanduser("~/orangead/macos-api/macos_api/bin/smctemp"),
        "smctemp"
    ]
    
    # Check if we have access to real SMC temperature
    has_smc = False
    if os.path.exists(smctemp_path) and os.access(smctemp_path, os.X_OK):
        has_smc = True
        method = "smc_real"
    else:
        for path in fallback_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                has_smc = True
                method = "smc_real"
                break
    
    # Determine thermal health (only if we have real temperature data)
    thermal_health = "unknown"
    thermal_issues = []
    
    if thermal_state.get("thermal_pressure", False):
        thermal_health = "warning"
        thermal_issues.append("thermal_pressure_detected")
    
    if cpu_temp is not None:
        # Only determine health if we have real temperature data
        thermal_health = "good"
        if cpu_temp > 80:  # High temperature threshold
            thermal_health = "critical"
            thermal_issues.append("high_cpu_temperature")
        elif cpu_temp > 70:  # Moderate temperature threshold
            thermal_health = "warning"
            thermal_issues.append("elevated_cpu_temperature")
    
    return {
        "timestamp": timestamp,
        "cpu_temperature": cpu_temp,
        "thermal_state": thermal_state,
        "thermal_health": thermal_health,
        "thermal_issues": thermal_issues,
        "temperature_unit": "celsius",
        "method": method,
        "capabilities": {
            "cpu_temperature": cpu_temp is not None,
            "thermal_state": bool(thermal_state.get("thermal_state")),
            "thermal_pressure_detection": True,
            "smc_available": has_smc
        }
    }