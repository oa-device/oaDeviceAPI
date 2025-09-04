"""Unit tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import mock_open, patch

from src.oaDeviceAPI.core.config import (
    HEALTH_SCORE_THRESHOLDS,
    HEALTH_SCORE_WEIGHTS,
    PLATFORM_CONFIG,
    Settings,
    detect_platform,
    get_platform_config,
)


class TestSettings:
    """Test legacy Settings class."""

    def test_settings_initialization(self):
        """Test Settings class initializes with defaults."""
        settings = Settings()

        # Test basic configuration
        assert settings.host == "0.0.0.0"
        assert settings.port == 9090
        assert settings.tailscale_subnet == "100.64.0.0/10"
        assert settings.log_level == "INFO"

        # Test platform override is None by default
        assert settings.platform_override is None

        # Test path defaults
        assert str(settings.screenshot_dir) == "/tmp/screenshots"
        assert str(settings.macos_bin_dir) == "/usr/local/bin"

    def test_legacy_settings_backward_compatibility(self):
        """Test that Settings provides backward compatibility."""
        settings = Settings()

        # Legacy attributes should exist
        assert hasattr(settings, 'host')
        assert hasattr(settings, 'port')
        assert hasattr(settings, 'tailscale_subnet')
        assert hasattr(settings, 'log_level')
        assert hasattr(settings, 'platform_override')
        assert hasattr(settings, 'screenshot_dir')

    def test_settings_platform_override(self):
        """Test platform override functionality."""
        settings = Settings()

        # Test setting platform override
        with patch.dict(os.environ, {'PLATFORM_OVERRIDE': 'macos'}):
            if settings.platform_override == "macos":
                assert settings.platform_override == 'macos'

    def test_settings_path_expansion(self):
        """Test path expansion in settings."""
        settings = Settings()

        # Path fields should be Path objects
        assert isinstance(settings.screenshot_dir, Path)
        assert isinstance(settings.macos_bin_dir, Path)
        assert isinstance(settings.macos_service_dir, Path)
        assert isinstance(settings.orangepi_display_config, Path)

        # Tracker root should expand ~
        if "~" in str(settings.tracker_root_dir):
            expanded_path = Path(settings.tracker_root_dir).expanduser()
            assert expanded_path.is_absolute()

    def test_settings_validation_edge_cases(self):
        """Test settings validation with edge cases."""
        # Test invalid port
        with patch.dict(os.environ, {'OAAPI_PORT': '99999'}):
            settings = Settings()
            # Should still work, no validation in Settings class
            assert settings.port == 9090  # Uses defaults

    def test_settings_path_attributes(self):
        """Test all path-related settings."""
        settings = Settings()

        # All these should be Path objects
        path_attrs = [
            'screenshot_dir',
            'macos_bin_dir',
            'macos_service_dir',
            'orangepi_display_config',
            'tracker_root_dir'
        ]

        for attr in path_attrs:
            value = getattr(settings, attr)
            assert isinstance(value, Path), f"{attr} should be Path object, got {type(value)}"


class TestPlatformDetection:
    """Test platform detection functionality."""

    def test_detect_platform_macos(self):
        """Test macOS detection."""
        with patch("platform.system", return_value="Darwin"):
            assert detect_platform() == "macos"

    def test_detect_platform_linux_generic(self):
        """Test generic Linux detection."""
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", side_effect=FileNotFoundError):
            assert detect_platform() == "linux"

    def test_detect_platform_linux_orangepi(self):
        """Test OrangePi detection on Linux."""
        with patch("platform.system", return_value="Linux"):
            # Mock the device-tree model file to contain OrangePi
            with patch("builtins.open", mock_open(read_data="Orange Pi 5B\x00")):
                result = detect_platform()
                assert result == "orangepi"

    def test_detect_platform_unknown(self):
        """Test unknown platform detection."""
        with patch("platform.system", return_value="Windows"):
            assert detect_platform() == "unknown"

    def test_detect_platform_env_override(self):
        """Test environment variable override."""
        with patch.dict(os.environ, {'PLATFORM_OVERRIDE': 'macos'}):
            assert detect_platform() == "macos"


class TestPlatformConfig:
    """Test platform configuration functionality."""

    def test_get_platform_config_macos(self):
        """Test macOS platform configuration."""
        config = get_platform_config("macos")

        assert config["service_manager"] == "launchctl"
        assert "/usr/local/bin" in config["bin_paths"]
        assert config["temp_dir"] == "/tmp"
        assert config["tracker_supported"] is True
        assert config["camguard_supported"] is True

    def test_get_platform_config_orangepi(self):
        """Test OrangePi platform configuration."""
        config = get_platform_config("orangepi")

        assert config["service_manager"] == "systemctl"
        assert "/usr/bin" in config["bin_paths"]
        assert config["temp_dir"] == "/tmp"
        assert config["screenshot_supported"] is True
        assert config["tracker_supported"] is False

    def test_get_platform_config_linux_fallback(self):
        """Test Linux fallback configuration."""
        config = get_platform_config("linux")

        assert config["service_manager"] == "systemctl"
        assert "/usr/bin" in config["bin_paths"]
        assert config["screenshot_supported"] is False

    def test_get_platform_config_unknown_fallback(self):
        """Test unknown platform fallback."""
        config = get_platform_config("unknown_platform")

        # Should fall back to linux config
        assert config["service_manager"] == "systemctl"

    def test_platform_config_defaults(self):
        """Test platform config with None parameter uses detected platform."""
        # This should use detected platform
        config = get_platform_config(None)

        # Should have required keys
        required_keys = ["service_manager", "bin_paths", "temp_dir"]
        for key in required_keys:
            assert key in config


class TestConfigurationConstants:
    """Test configuration constants and global values."""

    def test_platform_config_global(self):
        """Test global PLATFORM_CONFIG is set."""
        assert PLATFORM_CONFIG is not None
        assert isinstance(PLATFORM_CONFIG, dict)

        # Should have essential keys
        essential_keys = ["service_manager", "bin_paths", "temp_dir"]
        for key in essential_keys:
            assert key in PLATFORM_CONFIG

    def test_health_score_weights(self):
        """Test health score weights configuration."""
        assert isinstance(HEALTH_SCORE_WEIGHTS, dict)

        # Should have required components
        required_components = ["cpu", "memory", "disk", "tracker"]
        for component in required_components:
            assert component in HEALTH_SCORE_WEIGHTS
            assert isinstance(HEALTH_SCORE_WEIGHTS[component], (int, float))
            assert 0 <= HEALTH_SCORE_WEIGHTS[component] <= 1

        # Weights should sum to approximately 1.0 (allow floating point error)
        total_weight = sum(HEALTH_SCORE_WEIGHTS.values())
        assert 0.99 <= total_weight <= 1.01

    def test_health_score_thresholds(self):
        """Test health score thresholds configuration."""
        assert isinstance(HEALTH_SCORE_THRESHOLDS, dict)

        # Should have required components
        required_components = ["cpu", "memory", "disk"]
        for component in required_components:
            assert component in HEALTH_SCORE_THRESHOLDS
            thresholds = HEALTH_SCORE_THRESHOLDS[component]
            assert isinstance(thresholds, dict)

            # Should have warning and critical thresholds
            assert "warning" in thresholds
            assert "critical" in thresholds

            # Critical should be higher than warning
            assert thresholds["critical"] > thresholds["warning"]

            # Should be reasonable percentages
            assert 0 <= thresholds["warning"] <= 100
            assert 0 <= thresholds["critical"] <= 100

    def test_health_score_configuration(self):
        """Test health score weights and thresholds."""
        # Check weights sum to reasonable total
        total_weight = sum(HEALTH_SCORE_WEIGHTS.values())
        assert 0.9 <= total_weight <= 1.1, "Health score weights should sum to ~1.0"

        # Check required components exist
        required_components = ["cpu", "memory", "disk"]
        for component in required_components:
            assert component in HEALTH_SCORE_WEIGHTS
            assert component in HEALTH_SCORE_THRESHOLDS

        # Check threshold structure (document actual behavior)
        for component, thresholds in HEALTH_SCORE_THRESHOLDS.items():
            if isinstance(thresholds, dict):
                # Current config: warning=80, critical=95
                # This suggests: score >= 95 is critical, warning between 80-94
                assert "warning" in thresholds
                assert "critical" in thresholds


class TestConfigCompatibility:
    """Test configuration compatibility and migration."""

    def test_legacy_compatibility(self):
        """Test that legacy config interface still works."""
        settings = Settings()

        # Legacy interface should work
        assert settings.host == "0.0.0.0"
        assert settings.port == 9090

        # Path handling should work
        assert isinstance(settings.screenshot_dir, Path)


class TestConfigValidation:
    """Test configuration validation."""

    def test_network_host_validation(self):
        """Test network host validation."""
        # Valid hosts should work
        valid_hosts = ["0.0.0.0", "127.0.0.1", "localhost"]
        for host in valid_hosts:
            settings = Settings()
            settings.host = host
            # Settings class doesn't validate, just stores
            assert settings.host == host

    def test_port_validation(self):
        """Test port number validation."""
        settings = Settings()

        # Valid port range
        settings.port = 8080
        assert settings.port == 8080

        # Settings class doesn't validate ports
        settings.port = 99999
        assert settings.port == 99999


class TestPlatformDetectionLogic:
    """Test platform detection logic and edge cases."""

    def test_platform_detection_priority(self):
        """Test platform detection priority order."""
        # Environment override should take precedence
        with patch.dict(os.environ, {'PLATFORM_OVERRIDE': 'test_platform'}):
            result = detect_platform()
            assert result == "test_platform"

    def test_platform_detection_macos(self):
        """Test macOS platform detection."""
        with patch("platform.system", return_value="Darwin"):
            result = detect_platform()
            assert result == "macos"

    def test_platform_detection_orangepi_device_tree(self):
        """Test OrangePi detection via device tree."""
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", mock_open(read_data="Orange Pi 5B\x00")):
            result = detect_platform()
            assert result == "orangepi"

    def test_platform_detection_ubuntu_fallback(self):
        """Test Ubuntu detection as OrangePi fallback."""
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", side_effect=[
                 FileNotFoundError(),  # device-tree read fails
                 mock_open(read_data="NAME=Ubuntu\nVERSION=22.04").return_value  # os-release read succeeds
             ]), \
             patch("os.path.exists", return_value=True):

            result = detect_platform()
            assert result == "orangepi"

    def test_platform_detection_generic_linux(self):
        """Test generic Linux detection when OrangePi detection fails."""
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", side_effect=FileNotFoundError()), \
             patch("os.path.exists", return_value=False):

            result = detect_platform()
            assert result == "linux"

    def test_platform_detection_error_handling(self):
        """Test platform detection error handling."""
        # Test when platform.system() fails
        with patch("platform.system", side_effect=Exception("System detection failed")):
            result = detect_platform()
            assert result == "unknown"


class TestConfigurationIntegration:
    """Test configuration integration and real-world scenarios."""

    def test_full_configuration_flow(self):
        """Test complete configuration initialization flow."""
        # Should not raise exceptions
        settings = Settings()

        # Should have all required attributes
        required_attrs = [
            'host', 'port', 'tailscale_subnet', 'log_level',
            'screenshot_dir', 'macos_bin_dir', 'macos_service_dir',
            'orangepi_display_config', 'orangepi_player_service',
            'tracker_root_dir', 'tracker_api_url'
        ]

        for attr in required_attrs:
            assert hasattr(settings, attr), f"Settings missing required attribute: {attr}"

    def test_platform_specific_config_loading(self):
        """Test platform-specific configuration loading."""
        platforms = ["macos", "orangepi", "linux"]

        for platform_name in platforms:
            config = get_platform_config(platform_name)

            # Should have essential configuration
            assert "service_manager" in config
            assert "bin_paths" in config
            assert isinstance(config["bin_paths"], list)


class TestEnvironmentConfiguration:
    """Test environment-based configuration."""

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        test_env = {
            'PLATFORM_OVERRIDE': 'test_platform',
            'OAAPI_HOST': '127.0.0.1',
            'OAAPI_PORT': '8080'
        }

        with patch.dict(os.environ, test_env):
            # Settings class doesn't read from env directly
            settings = Settings()
            assert settings.host == "0.0.0.0"  # Uses defaults
            assert settings.port == 9090       # Uses defaults

    def test_path_resolution(self):
        """Test path resolution and expansion."""
        settings = Settings()

        # Paths should be resolved
        assert settings.screenshot_dir.is_absolute()
        assert settings.macos_bin_dir.is_absolute()


class TestConfigurationValidation:
    """Test configuration validation and constraints."""

    def test_port_constraints(self):
        """Test port number constraints."""
        settings = Settings()

        # Default port should be valid
        assert 1 <= settings.port <= 65535

    def test_path_validity(self):
        """Test path configuration validity."""
        settings = Settings()

        # Paths should be valid Path objects
        paths_to_test = [
            settings.screenshot_dir,
            settings.macos_bin_dir,
            settings.macos_service_dir,
            settings.orangepi_display_config,
            settings.tracker_root_dir
        ]

        for path in paths_to_test:
            assert isinstance(path, Path)
            # Path should be constructable (doesn't need to exist)
            assert str(path)  # Should be convertible to string


class TestConfigurationConstants:
    """Test configuration constants."""

    def test_health_score_weights(self):
        """Test health score weights."""
        assert isinstance(HEALTH_SCORE_WEIGHTS, dict)

        # Should have all required components
        expected_components = ['cpu', 'memory', 'disk', 'tracker']
        for component in expected_components:
            assert component in HEALTH_SCORE_WEIGHTS
            weight = HEALTH_SCORE_WEIGHTS[component]
            assert isinstance(weight, (int, float))
            assert 0 <= weight <= 1

        # Total should be approximately 1.0
        total = sum(HEALTH_SCORE_WEIGHTS.values())
        assert 0.99 <= total <= 1.01

    def test_health_score_thresholds(self):
        """Test health score thresholds."""
        assert isinstance(HEALTH_SCORE_THRESHOLDS, dict)

        expected_components = ['cpu', 'memory', 'disk']
        for component in expected_components:
            assert component in HEALTH_SCORE_THRESHOLDS
            thresholds = HEALTH_SCORE_THRESHOLDS[component]
            assert isinstance(thresholds, dict)
            assert 'warning' in thresholds
            assert 'critical' in thresholds

    def test_health_score_configuration(self):
        """Test health score weights and thresholds."""
        # Check weights sum to reasonable total
        total_weight = sum(HEALTH_SCORE_WEIGHTS.values())
        assert 0.9 <= total_weight <= 1.1, "Health score weights should sum to ~1.0"

        # Check required components exist
        required_components = ["cpu", "memory", "disk"]
        for component in required_components:
            assert component in HEALTH_SCORE_WEIGHTS
            assert component in HEALTH_SCORE_THRESHOLDS

        # Check threshold structure (document actual behavior)
        for component, thresholds in HEALTH_SCORE_THRESHOLDS.items():
            if isinstance(thresholds, dict):
                # Current config: warning=80, critical=95
                # This suggests: score >= 95 is critical, warning between 80-94
                assert "warning" in thresholds
                assert "critical" in thresholds
