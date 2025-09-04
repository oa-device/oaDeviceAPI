"""Platform detection and management utilities."""

import logging
import subprocess

from .config import DETECTED_PLATFORM, get_platform_config

logger = logging.getLogger(__name__)


class PlatformManager:
    """Manages platform-specific operations and feature availability."""

    def __init__(self):
        self.platform = DETECTED_PLATFORM
        self.config = get_platform_config(self.platform)
        logger.info(f"Detected platform: {self.platform}")

    def is_macos(self) -> bool:
        """Check if running on macOS."""
        return self.platform == "macos"

    def is_orangepi(self) -> bool:
        """Check if running on OrangePi."""
        return self.platform == "orangepi"

    def is_linux(self) -> bool:
        """Check if running on Linux (generic)."""
        return self.platform in ["linux", "orangepi"]

    def supports_feature(self, feature: str) -> bool:
        """Check if the current platform supports a specific feature."""
        return self.config.get(f"{feature}_supported", False)

    def get_service_manager(self) -> str:
        """Get the service manager for the current platform."""
        return self.config["service_manager"]

    def get_bin_paths(self) -> list[str]:
        """Get binary search paths for the current platform."""
        return self.config["bin_paths"]

    def get_temp_dir(self) -> str:
        """Get temporary directory for the current platform."""
        return self.config["temp_dir"]

    def check_service_status(self, service_name: str) -> bool | None:
        """Check if a service is running on the current platform."""
        try:
            if self.is_macos():
                # Use launchctl for macOS
                cmd = ["launchctl", "print", f"gui/{subprocess.getoutput('id -u')}/{service_name}"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                return "state = running" in result.stdout
            else:
                # Use systemctl for Linux
                cmd = ["systemctl", "is-active", service_name]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                return result.stdout.strip() == "active"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            logger.warning(f"Could not check status of service {service_name}")
            return None

    def restart_service(self, service_name: str) -> bool:
        """Restart a service on the current platform."""
        try:
            if self.is_macos():
                # Use launchctl for macOS
                stop_cmd = ["launchctl", "stop", service_name]
                start_cmd = ["launchctl", "start", service_name]

                subprocess.run(stop_cmd, capture_output=True, timeout=10)
                result = subprocess.run(start_cmd, capture_output=True, timeout=10)
                return result.returncode == 0
            else:
                # Use systemctl for Linux
                cmd = ["sudo", "systemctl", "restart", service_name]
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            logger.error(f"Failed to restart service {service_name}")
            return False

    def get_available_features(self) -> dict[str, bool]:
        """Get all available features for the current platform."""
        features = [
            "screenshot",
            "camera",
            "tracker",
            "camguard"
        ]
        return {feature: self.supports_feature(feature) for feature in features}

    def get_platform_info(self) -> dict[str, any]:
        """Get comprehensive platform information."""
        return {
            "platform": self.platform,
            "service_manager": self.get_service_manager(),
            "bin_paths": self.get_bin_paths(),
            "temp_dir": self.get_temp_dir(),
            "features": self.get_available_features(),
            "config": self.config
        }


# Global platform manager instance
platform_manager = PlatformManager()
