"""Configuration management for oaDeviceAPI."""

import os
import platform
from pathlib import Path
from typing import Optional

from .config_schema import AppConfig, Platform, ServiceManager

# App version
APP_VERSION = "1.0.0"


def detect_platform() -> str:
    """Detect the current platform."""
    # Check for manual override first
    platform_override = os.getenv("PLATFORM_OVERRIDE")
    if platform_override:
        return platform_override.lower()
    
    # Detect based on system
    system = platform.system().lower()
    
    if system == "darwin":
        return "macos"
    elif system == "linux":
        # Try to detect if it's an OrangePi
        try:
            # Check for OrangePi-specific files or hardware
            with open("/proc/device-tree/model", "r") as f:
                model = f.read().strip()
                if "orange" in model.lower() or "pi" in model.lower():
                    return "orangepi"
        except (FileNotFoundError, PermissionError):
            pass
        
        # Check for Ubuntu/Debian (common on OrangePi)
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    content = f.read().lower()
                    if "ubuntu" in content or "debian" in content:
                        return "orangepi"  # Assume OrangePi for Ubuntu/Debian
            except (FileNotFoundError, PermissionError):
                pass
                
        return "linux"  # Generic Linux fallback
    
    return "unknown"


def get_platform_config(platform_name: str) -> dict:
    """Get configuration for the specified platform."""
    platform_configs = {
        "macos": {
            "service_manager": ServiceManager.LAUNCHCTL,
            "bin_paths": [Path("/usr/local/bin"), Path("/opt/homebrew/bin")],
            "temp_dir": Path("/tmp"),
            "screenshot_supported": False,
            "camera_supported": True,
            "tracker_supported": True,
            "camguard_supported": True,
        },
        "orangepi": {
            "service_manager": ServiceManager.SYSTEMCTL,
            "bin_paths": [Path("/usr/bin"), Path("/usr/local/bin")],
            "temp_dir": Path("/tmp"),
            "screenshot_supported": True,
            "camera_supported": False,
            "tracker_supported": False,
            "camguard_supported": False,
        },
        "linux": {
            "service_manager": ServiceManager.SYSTEMCTL,
            "bin_paths": [Path("/usr/bin"), Path("/usr/local/bin")],
            "temp_dir": Path("/tmp"),
            "screenshot_supported": False,
            "camera_supported": False,
            "tracker_supported": False,
            "camguard_supported": False,
        }
    }
    
    return platform_configs.get(platform_name.lower(), platform_configs["linux"])


# Initialize configuration with platform detection
detected_platform = detect_platform()
platform_config = get_platform_config(detected_platform)

# Create app configuration with platform-specific defaults
config_defaults = {
    "app_version": APP_VERSION,
    "platform": {
        "platform": detected_platform,
        "service_manager": platform_config["service_manager"],
        "bin_paths": platform_config["bin_paths"],
        "temp_dir": platform_config["temp_dir"],
    }
}

# Global settings instance with validated configuration
settings = AppConfig(**config_defaults)

# Backward compatibility - export commonly used values
DETECTED_PLATFORM = settings.platform.platform
PLATFORM_CONFIG = platform_config

# Legacy exports for backward compatibility
TRACKER_ROOT = settings.services.tracker_root_dir
TRACKER_API_URL = settings.services.tracker_api_url
CACHE_TTL = settings.cache.default_ttl
HEALTH_SCORE_WEIGHTS = settings.get_health_weights()
HEALTH_SCORE_THRESHOLDS = settings.get_health_thresholds()

# Command constants for macOS compatibility
LAUNCHCTL_CMD = "/bin/launchctl"
PS_CMD = "/bin/ps"
READLINK_CMD = "/usr/bin/readlink"
PYTHON_CMD = "/usr/bin/python3"