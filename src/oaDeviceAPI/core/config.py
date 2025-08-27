"""Configuration management for oaDeviceAPI."""

import os
import platform
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

APP_VERSION = "1.0.0"


class Settings(BaseSettings):
    """Application settings with platform detection."""
    
    # API Configuration
    host: str = Field(default="0.0.0.0", env="OAAPI_HOST")
    port: int = Field(default=9090, env="OAAPI_PORT")
    
    # Security
    tailscale_subnet: str = Field(default="100.64.0.0/10", env="TAILSCALE_SUBNET")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Platform Detection (auto-detected, but can be overridden)
    platform_override: Optional[str] = Field(default=None, env="PLATFORM_OVERRIDE")
    
    # Platform-specific paths and configuration
    screenshot_dir: Path = Field(default=Path("/tmp/screenshots"))
    service_timeout: int = Field(default=30)
    
    # macOS specific
    macos_bin_dir: Path = Field(default=Path("/usr/local/bin"))
    macos_service_dir: Path = Field(default=Path.home() / "Library/LaunchAgents")
    
    # OrangePi specific  
    orangepi_display_config: Path = Field(default=Path("/etc/orangead/display.conf"))
    orangepi_player_service: str = Field(default="slideshow-player.service")
    
    # macOS specific paths
    tracker_root_dir: str = Field(default="~/orangead/tracker", env="TRACKER_ROOT_DIR")
    tracker_api_url: str = Field(default="http://localhost:8080", env="TRACKER_API_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def detect_platform() -> str:
    """Detect the current platform."""
    settings = Settings()
    
    # Check for manual override first
    if settings.platform_override:
        return settings.platform_override.lower()
    
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


# Global settings instance
settings = Settings()

# Detected platform
DETECTED_PLATFORM = detect_platform()

# Platform-specific configuration
PLATFORM_CONFIG = {
    "macos": {
        "bin_paths": ["/usr/local/bin", "/opt/homebrew/bin"],
        "service_manager": "launchctl",
        "temp_dir": "/tmp",
        "screenshot_supported": False,
        "camera_supported": True,
        "tracker_supported": True,
        "camguard_supported": True,
    },
    "orangepi": {
        "bin_paths": ["/usr/bin", "/usr/local/bin"],
        "service_manager": "systemctl",
        "temp_dir": "/tmp",
        "screenshot_supported": True,
        "camera_supported": False,
        "tracker_supported": False,
        "camguard_supported": False,
    },
    "linux": {
        "bin_paths": ["/usr/bin", "/usr/local/bin"],
        "service_manager": "systemctl",
        "temp_dir": "/tmp",
        "screenshot_supported": False,
        "camera_supported": False,
        "tracker_supported": False,
        "camguard_supported": False,
    }
}

def get_platform_config() -> dict:
    """Get configuration for the detected platform."""
    return PLATFORM_CONFIG.get(DETECTED_PLATFORM, PLATFORM_CONFIG["linux"])


# Command constants for macOS compatibility
LAUNCHCTL_CMD = "/bin/launchctl"
PS_CMD = "/bin/ps"
READLINK_CMD = "/usr/bin/readlink"
PYTHON_CMD = "/usr/bin/python3"

# Tracker root path
from pathlib import Path
TRACKER_ROOT = Path(os.path.expanduser(settings.tracker_root_dir))

# API URLs  
TRACKER_API_URL = settings.tracker_api_url

# Cache settings
CACHE_TTL = getattr(settings, 'service_timeout', 30)

# Health score settings
HEALTH_SCORE_WEIGHTS = {
    "cpu": 0.25,
    "memory": 0.25,
    "disk": 0.25,
    "tracker": 0.25
}

HEALTH_SCORE_THRESHOLDS = {
    "cpu": {"good": 80, "warning": 90},
    "memory": {"good": 80, "warning": 90},  
    "disk": {"good": 85, "warning": 95},
    "tracker": {"good": 1.0, "warning": 0.5}
}