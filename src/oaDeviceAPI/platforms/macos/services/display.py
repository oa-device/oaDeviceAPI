import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ....core.config import PYTHON_CMD, TRACKER_ROOT
from ..services.utils import run_command


def get_display_info() -> Dict:
    """Get display configuration and status for macOS.

    This function uses multiple methods to detect displays and determine
    if the Mac is headless, providing detailed information about connected displays.

    Returns:
        Dict with display information including headless status
    """
    display_info = {
        "connected": False,
        "is_headless": True,  # Default to headless until proven otherwise
        "resolution": "unknown",
        "refresh_rate": "unknown",
        "vendor": "unknown",
        "model": "unknown",
        "displays": [],
        "detection_method": "none",
    }

    # Method 1: Use system_profiler (most reliable but slower)
    try:
        cmd = ["system_profiler", "SPDisplaysDataType", "-json"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=5
        )

        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                displays_data = data.get("SPDisplaysDataType", [])

                # Check if we have actual display devices (not just graphics cards)
                real_displays = []
                for display in displays_data:
                    # Skip entries that are just graphics cards without displays
                    if "spdisplays_resolution" in display:
                        real_displays.append(display)

                if real_displays:
                    display_info["connected"] = True
                    display_info["is_headless"] = False
                    display_info["detection_method"] = "system_profiler"

                    # Process each display
                    displays = []
                    for display in real_displays:
                        display_details = {}

                        # Extract resolution
                        resolution = display.get("spdisplays_resolution", "unknown")
                        if isinstance(resolution, str) and "x" in resolution:
                            display_details["resolution"] = resolution

                        # Extract refresh rate
                        refresh_rate = display.get("spdisplays_refresh", "unknown")
                        if refresh_rate:
                            display_details["refresh_rate"] = refresh_rate

                        # Extract vendor/model
                        vendor = display.get("spdisplays_vendor", "unknown")
                        if vendor:
                            display_details["vendor"] = vendor

                        model = display.get("spdisplays_device_name", "unknown")
                        if model:
                            display_details["model"] = model

                        # Extract connection type
                        connection = display.get(
                            "spdisplays_connection_type", "unknown"
                        )
                        if connection:
                            display_details["connection"] = connection

                        # Add to displays list
                        displays.append(display_details)

                    display_info["displays"] = displays

                    # Set primary display info if available
                    if displays:
                        primary = displays[0]  # Assume first display is primary
                        display_info["resolution"] = primary.get(
                            "resolution", "unknown"
                        )
                        display_info["refresh_rate"] = primary.get(
                            "refresh_rate", "unknown"
                        )
                        display_info["vendor"] = primary.get("vendor", "unknown")
                        display_info["model"] = primary.get("model", "unknown")
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"Error getting display info via system_profiler: {e}")

    # Method 2: If still headless, try using ioreg as a backup method
    if display_info["is_headless"]:
        try:
            cmd = ["ioreg", "-l", "-d", "2", "-c", "IODisplay"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=3
            )

            if result.returncode == 0 and "IODisplayConnect" in result.stdout:
                # IODisplayConnect presence indicates a display is connected
                display_info["connected"] = True
                display_info["is_headless"] = False
                display_info["detection_method"] = "ioreg"
        except Exception as e:
            print(f"Error getting display info via ioreg: {e}")

    # Method 3: Try CGDisplayBounds via Python script as a last resort
    if display_info["is_headless"]:
        try:
            # Create a temporary Python script that uses Objective-C bridge
            script_content = """
#!/usr/bin/env python3
import json
from ctypes import cdll, c_int32, POINTER, Structure

class CGRect(Structure):
    _fields_ = [("origin_x", c_int32), ("origin_y", c_int32), ("width", c_int32), ("height", c_int32)]

try:
    # Load CoreGraphics framework
    core_graphics = cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    
    # Get number of displays
    CGGetActiveDisplayList = core_graphics.CGGetActiveDisplayList
    CGGetActiveDisplayList.argtypes = [c_int32, POINTER(c_int32), POINTER(c_int32)]
    CGGetActiveDisplayList.restype = c_int32
    
    # Get display bounds
    CGDisplayBounds = core_graphics.CGDisplayBounds
    CGDisplayBounds.argtypes = [c_int32]
    CGDisplayBounds.restype = CGRect
    
    # Get active displays
    max_displays = 16
    display_count = c_int32(0)
    display_list = (c_int32 * max_displays)()
    
    result = CGGetActiveDisplayList(max_displays, display_list, display_count)
    
    if result == 0 and display_count.value > 0:
        displays = []
        for i in range(display_count.value):
            display_id = display_list[i]
            bounds = CGDisplayBounds(display_id)
            displays.append({
                "id": display_id,
                "bounds": {
                    "x": bounds.origin_x,
                    "y": bounds.origin_y,
                    "width": bounds.width,
                    "height": bounds.height
                }
            })
        
        print(json.dumps({"success": True, "displays": displays, "count": display_count.value}))
    else:
        print(json.dumps({"success": False, "error": "No displays found"}))
        
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
"""

            # Write script to temporary file
            temp_script = Path("/tmp/check_displays.py")
            temp_script.write_text(script_content)
            temp_script.chmod(0o755)

            # Execute script
            result = subprocess.run(
                [str(temp_script)],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
            temp_script.unlink(missing_ok=True)

            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if data.get("success") and data.get("count", 0) > 0:
                        display_info["connected"] = True
                        display_info["is_headless"] = False
                        display_info["detection_method"] = "coregraphics"

                        # Add display information
                        cg_displays = []
                        for display in data.get("displays", []):
                            bounds = display.get("bounds", {})
                            if (
                                bounds.get("width", 0) > 0
                                and bounds.get("height", 0) > 0
                            ):
                                cg_displays.append(
                                    {
                                        "resolution": f"{bounds.get('width')}x{bounds.get('height')}",
                                        "id": display.get("id"),
                                        "bounds": bounds,
                                    }
                                )

                        # If we have display info from CoreGraphics but not from system_profiler
                        if cg_displays and not display_info["displays"]:
                            display_info["displays"] = cg_displays

                            # Set primary display resolution if available
                            if cg_displays:
                                primary = cg_displays[0]
                                if "resolution" in primary:
                                    display_info["resolution"] = primary["resolution"]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Error getting display info via CoreGraphics: {e}")

    # Final headless determination
    display_info["is_headless"] = not display_info["connected"]

    return display_info
