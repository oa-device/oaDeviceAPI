"""Configuration management for oaDeviceAPI."""

import os
import platform
from pathlib import Path

from .config_schema import AppConfig

# App version
APP_VERSION = "1.0.0"


def detect_platform() -> str:
    """Detect the current platform."""
    try:
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
                with open("/proc/device-tree/model") as f:
                    model = f.read().strip()
                    if "orange" in model.lower() or "pi" in model.lower():
                        return "orangepi"
            except (FileNotFoundError, PermissionError):
                pass

            # Check for Ubuntu/Debian (common on OrangePi)
            if os.path.exists("/etc/os-release"):
                try:
                    with open("/etc/os-release") as f:
                        content = f.read().lower()
                        if "ubuntu" in content or "debian" in content:
                            return "orangepi"  # Assume OrangePi for Ubuntu/Debian
                except (FileNotFoundError, PermissionError):
                    pass

            return "linux"  # Generic Linux fallback

        return "unknown"
    except Exception:
        # If any exception occurs in platform detection, return unknown
        return "unknown"


def get_platform_config(platform_name: str | None = None) -> dict:
    """Get configuration for the specified platform."""
    if platform_name is None:
        platform_name = DETECTED_PLATFORM

    platform_configs = {
        "macos": {
            "service_manager": "launchctl",
            "bin_paths": ["/usr/local/bin", "/opt/homebrew/bin"],
            "temp_dir": "/tmp",
            "screenshot_supported": False,
            "camera_supported": True,
            "tracker_supported": True,
            "camguard_supported": True,
        },
        "orangepi": {
            "service_manager": "systemctl",
            "bin_paths": ["/usr/bin", "/usr/local/bin"],
            "temp_dir": "/tmp",
            "screenshot_supported": True,
            "camera_supported": False,
            "tracker_supported": False,
            "camguard_supported": False,
        },
        "linux": {
            "service_manager": "systemctl",
            "bin_paths": ["/usr/bin", "/usr/local/bin"],
            "temp_dir": "/tmp",
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


class Settings:
    """Legacy Settings class for backward compatibility."""

    def __init__(self):
        self.host = "0.0.0.0"
        self.port = 9090
        self.tailscale_subnet = "100.64.0.0/10"
        self.log_level = "INFO"
        self.platform_override = None
        self.screenshot_dir = Path("/tmp/screenshots")
        self.macos_bin_dir = Path("/usr/local/bin")
        self.macos_service_dir = Path.home() / "Library/LaunchAgents"
        self.orangepi_display_config = Path("/etc/orangead/display.conf")
        self.orangepi_player_service = "slideshow-player.service"
        self.tracker_root_dir = Path("~/orangead/tracker")
        self.tracker_api_url = "http://localhost:8080"


# Create both legacy settings and modern app config for different use cases
settings = Settings()

# Create modern AppConfig for new architecture components
try:
    app_config = AppConfig()
except Exception:
    # If AppConfig initialization fails, create minimal version
    app_config = AppConfig(
        app_version=APP_VERSION,
        environment="development"
    )

# Backward compatibility - export commonly used values
DETECTED_PLATFORM = detected_platform
PLATFORM_CONFIG = platform_config

# Legacy exports for backward compatibility
TRACKER_ROOT = settings.tracker_root_dir
TRACKER_API_URL = settings.tracker_api_url
CACHE_TTL = 30

# Health scoring configuration
HEALTH_SCORE_WEIGHTS = {
    'cpu': 0.25,
    'memory': 0.25,
    'disk': 0.25,
    'tracker': 0.25,
}

HEALTH_SCORE_THRESHOLDS = {
    'cpu': {'warning': 80, 'critical': 95},
    'memory': {'warning': 80, 'critical': 95},
    'disk': {'warning': 85, 'critical': 95},
}

# Command constants for macOS compatibility
LAUNCHCTL_CMD = "/bin/launchctl"
PS_CMD = "/bin/ps"
READLINK_CMD = "/usr/bin/readlink"
PYTHON_CMD = "/usr/bin/python3"
