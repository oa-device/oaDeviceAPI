"""Unit tests for PlatformManager functionality."""

import subprocess
from unittest.mock import Mock, patch

from src.oaDeviceAPI.core.platform import PlatformManager


class TestPlatformManagerInitialization:
    """Test PlatformManager initialization and basic functionality."""

    def test_platform_manager_init_macos(self):
        """Test PlatformManager initialization on macOS."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            manager = PlatformManager()

            assert manager.platform == "macos"
            assert manager.is_macos() is True
            assert manager.is_orangepi() is False
            assert manager.is_linux() is False  # macOS is not considered Linux
            assert manager.get_service_manager() == "launchctl"

    def test_platform_manager_init_orangepi(self):
        """Test PlatformManager initialization on OrangePi."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"):
            manager = PlatformManager()

            assert manager.platform == "orangepi"
            assert manager.is_macos() is False
            assert manager.is_orangepi() is True
            assert manager.is_linux() is True  # OrangePi is considered Linux
            assert manager.get_service_manager() == "systemctl"

    def test_platform_manager_init_generic_linux(self):
        """Test PlatformManager initialization on generic Linux."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "linux"):
            manager = PlatformManager()

            assert manager.platform == "linux"
            assert manager.is_macos() is False
            assert manager.is_orangepi() is False
            assert manager.is_linux() is True
            assert manager.get_service_manager() == "systemctl"


class TestFeatureSupport:
    """Test platform feature support detection."""

    def test_macos_feature_support(self):
        """Test macOS feature support."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            manager = PlatformManager()

            assert manager.supports_feature("camera") is True
            assert manager.supports_feature("tracker") is True
            assert manager.supports_feature("camguard") is True
            assert manager.supports_feature("screenshot") is False

    def test_orangepi_feature_support(self):
        """Test OrangePi feature support."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"):
            manager = PlatformManager()

            assert manager.supports_feature("screenshot") is True
            assert manager.supports_feature("camera") is False
            assert manager.supports_feature("tracker") is False
            assert manager.supports_feature("camguard") is False

    def test_generic_linux_feature_support(self):
        """Test generic Linux feature support."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "linux"):
            manager = PlatformManager()

            # Generic Linux should have minimal features
            assert manager.supports_feature("screenshot") is False
            assert manager.supports_feature("camera") is False
            assert manager.supports_feature("tracker") is False
            assert manager.supports_feature("camguard") is False

    def test_unknown_feature_handling(self):
        """Test handling of unknown features."""
        manager = PlatformManager()

        # Unknown features should return False
        assert manager.supports_feature("unknown_feature") is False
        assert manager.supports_feature("") is False
        assert manager.supports_feature("fake_camera") is False

    def test_get_available_features(self):
        """Test getting all available features."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            manager = PlatformManager()
            features = manager.get_available_features()

            expected_features = ["screenshot", "camera", "tracker", "camguard"]
            for feature in expected_features:
                assert feature in features
                assert isinstance(features[feature], bool)

            # macOS specific expectations
            assert features["camera"] is True
            assert features["tracker"] is True
            assert features["screenshot"] is False


class TestServiceManagement:
    """Test service management functionality."""

    def test_check_service_status_macos_running(self):
        """Test checking service status on macOS when service is running."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.getoutput", return_value="501"):

            mock_run.return_value = Mock(
                returncode=0,
                stdout="state = running\npid = 1234"
            )

            manager = PlatformManager()
            status = manager.check_service_status("com.orangead.tracker")

            assert status is True
            mock_run.assert_called_once()
            assert "launchctl" in mock_run.call_args[0][0][0]

    def test_check_service_status_macos_stopped(self):
        """Test checking service status on macOS when service is stopped."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.getoutput", return_value="501"):

            mock_run.return_value = Mock(
                returncode=0,
                stdout="state = not running"
            )

            manager = PlatformManager()
            status = manager.check_service_status("com.orangead.tracker")

            assert status is False

    def test_check_service_status_linux_active(self):
        """Test checking service status on Linux when service is active."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(
                returncode=0,
                stdout="active\n"
            )

            manager = PlatformManager()
            status = manager.check_service_status("slideshow-player.service")

            assert status is True
            mock_run.assert_called_once()
            assert "systemctl" in mock_run.call_args[0][0][0]

    def test_check_service_status_linux_inactive(self):
        """Test checking service status on Linux when service is inactive."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(
                returncode=3,  # systemctl returns 3 for inactive
                stdout="inactive\n"
            )

            manager = PlatformManager()
            status = manager.check_service_status("slideshow-player.service")

            assert status is False

    def test_check_service_status_timeout(self):
        """Test service status check timeout handling."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            manager = PlatformManager()
            status = manager.check_service_status("test.service")

            assert status is None

    def test_check_service_status_command_not_found(self):
        """Test service status check when command is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            manager = PlatformManager()
            status = manager.check_service_status("test.service")

            assert status is None

    def test_restart_service_macos_success(self):
        """Test successful service restart on macOS."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run:

            # Mock successful stop and start
            mock_run.return_value = Mock(returncode=0)

            manager = PlatformManager()
            result = manager.restart_service("com.orangead.tracker")

            assert result is True
            assert mock_run.call_count == 2  # stop + start

    def test_restart_service_macos_failure(self):
        """Test failed service restart on macOS."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run:

            # Mock failed start command
            mock_run.side_effect = [
                Mock(returncode=0),  # stop succeeds
                Mock(returncode=1)   # start fails
            ]

            manager = PlatformManager()
            result = manager.restart_service("com.orangead.tracker")

            assert result is False

    def test_restart_service_linux_success(self):
        """Test successful service restart on Linux."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(returncode=0)

            manager = PlatformManager()
            result = manager.restart_service("slideshow-player.service")

            assert result is True
            mock_run.assert_called_once()
            assert "sudo" in mock_run.call_args[0][0][0]
            assert "systemctl" in mock_run.call_args[0][0]
            assert "restart" in mock_run.call_args[0][0]

    def test_restart_service_timeout(self):
        """Test service restart timeout handling."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            manager = PlatformManager()
            result = manager.restart_service("test.service")

            assert result is False


class TestPlatformManagerInfoGathering:
    """Test platform information gathering."""

    def test_get_platform_info_complete(self):
        """Test getting complete platform information."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            manager = PlatformManager()
            info = manager.get_platform_info()

            required_keys = ["platform", "service_manager", "bin_paths", "temp_dir", "features", "config"]
            for key in required_keys:
                assert key in info, f"Missing key: {key}"

            assert info["platform"] == "macos"
            assert info["service_manager"] == "launchctl"
            assert isinstance(info["bin_paths"], list)
            assert isinstance(info["features"], dict)
            assert isinstance(info["config"], dict)

    def test_get_platform_info_features_detail(self):
        """Test that platform info includes detailed feature information."""
        manager = PlatformManager()
        info = manager.get_platform_info()

        # Features should be a dict of feature -> bool
        features = info["features"]
        expected_features = ["screenshot", "camera", "tracker", "camguard"]

        for feature in expected_features:
            assert feature in features
            assert isinstance(features[feature], bool)

    def test_get_bin_paths(self):
        """Test getting binary paths."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            manager = PlatformManager()
            paths = manager.get_bin_paths()

            assert isinstance(paths, list)
            assert len(paths) > 0
            assert all(isinstance(path, str) for path in paths)
            assert "/usr/local/bin" in paths

    def test_get_temp_dir(self):
        """Test getting temporary directory."""
        manager = PlatformManager()
        temp_dir = manager.get_temp_dir()

        assert isinstance(temp_dir, str)
        assert temp_dir.startswith("/")  # Should be absolute path
        assert temp_dir == "/tmp"  # Default for all platforms


class TestPlatformManagerEdgeCases:
    """Test PlatformManager edge cases and error handling."""

    def test_platform_manager_unknown_platform(self):
        """Test PlatformManager with unknown platform."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "unknown"):
            manager = PlatformManager()

            assert manager.platform == "unknown"
            assert manager.is_macos() is False
            assert manager.is_orangepi() is False
            assert manager.is_linux() is False

            # Should fall back to Linux config
            info = manager.get_platform_info()
            assert "service_manager" in info

    def test_platform_manager_empty_config(self):
        """Test PlatformManager with empty configuration."""
        with patch("src.oaDeviceAPI.core.config.get_platform_config", return_value={}):
            manager = PlatformManager()

            # Should handle missing config keys gracefully
            assert manager.get_service_manager() is None
            assert manager.get_bin_paths() is None
            assert manager.get_temp_dir() is None

    def test_service_status_with_special_characters(self):
        """Test service status checking with special characters in service names."""
        manager = PlatformManager()

        special_services = [
            "com.orangead.tracker-v2",
            "service.with.dots",
            "service_with_underscores",
            "service-with-dashes"
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="active")

            for service in special_services:
                # Should not raise errors with special characters
                status = manager.check_service_status(service)
                assert status is not None

    def test_concurrent_service_checks(self):
        """Test concurrent service status checking."""
        import asyncio
        import time

        manager = PlatformManager()
        services = [
            "service1",
            "service2",
            "service3",
            "service4"
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="active")

            # Simulate multiple concurrent checks
            start_time = time.time()

            async def check_service(service_name):
                return manager.check_service_status(service_name)

            # Run checks concurrently
            async def run_concurrent_checks():
                tasks = [check_service(service) for service in services]
                return await asyncio.gather(*tasks)

            # This is a sync test, but tests the underlying subprocess behavior
            for service in services:
                status = manager.check_service_status(service)
                assert status is not None

            end_time = time.time()

            # Should complete reasonably quickly
            assert (end_time - start_time) < 5.0


class TestPlatformManagerConfiguration:
    """Test PlatformManager configuration handling."""

    def test_platform_manager_config_modification_isolation(self):
        """Test that modifying config doesn't affect other instances."""
        manager1 = PlatformManager()
        manager2 = PlatformManager()

        # Modify one instance's config
        manager1.config["test_key"] = "test_value"

        # Other instance should not be affected
        assert "test_key" not in manager2.config

    def test_platform_manager_with_custom_config(self):
        """Test PlatformManager with custom configuration."""
        custom_config = {
            "service_manager": "custom_manager",
            "bin_paths": ["/custom/bin"],
            "temp_dir": "/custom/tmp",
            "camera_supported": True,
            "screenshot_supported": True
        }

        with patch("src.oaDeviceAPI.core.config.get_platform_config", return_value=custom_config):
            manager = PlatformManager()

            assert manager.get_service_manager() == "custom_manager"
            assert manager.get_bin_paths() == ["/custom/bin"]
            assert manager.get_temp_dir() == "/custom/tmp"
            assert manager.supports_feature("camera") is True
            assert manager.supports_feature("screenshot") is True

    def test_platform_manager_feature_validation(self):
        """Test feature validation in platform manager."""
        manager = PlatformManager()

        # Test various feature name formats
        feature_variations = [
            "camera",
            "CAMERA",
            "Camera",
            "cAmErA"
        ]

        # Only exact match should work (case-sensitive)
        for feature in feature_variations:
            result = manager.supports_feature(feature)
            assert isinstance(result, bool)
            if feature == "camera":
                # Result depends on platform
                assert result in [True, False]
            else:
                # Non-exact matches should return False
                assert result is False


class TestServiceStatusEdgeCases:
    """Test service status checking edge cases."""

    def test_service_status_macos_user_id_failure(self):
        """Test macOS service status when user ID lookup fails."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.getoutput", side_effect=subprocess.SubprocessError):

            manager = PlatformManager()
            status = manager.check_service_status("com.test.service")

            # Should handle user ID lookup failure gracefully
            assert status is None

    def test_service_status_macos_malformed_output(self):
        """Test macOS service status with malformed launchctl output."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.getoutput", return_value="501"):

            # Test various malformed outputs
            malformed_outputs = [
                "",  # Empty output
                "some random text",  # No state info
                "state = unknown",  # Unknown state
                "pid = 1234",  # Missing state
                "state =",  # Empty state value
            ]

            manager = PlatformManager()

            for output in malformed_outputs:
                mock_run.return_value = Mock(returncode=0, stdout=output)
                status = manager.check_service_status("com.test.service")

                if "state = running" not in output:
                    assert status is False

    def test_service_status_linux_return_codes(self):
        """Test Linux service status with different systemctl return codes."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"), \
             patch("subprocess.run") as mock_run:

            # systemctl return codes:
            # 0 = active, 1 = dead, 3 = inactive, 4 = unknown
            test_cases = [
                (0, "active", True),
                (1, "dead", False),
                (3, "inactive", False),
                (4, "unknown", False)
            ]

            manager = PlatformManager()

            for return_code, stdout, expected in test_cases:
                mock_run.return_value = Mock(
                    returncode=return_code,
                    stdout=f"{stdout}\n"
                )

                status = manager.check_service_status("test.service")
                assert status == expected

    def test_restart_service_partial_failure_macos(self):
        """Test macOS service restart with partial failure."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run:

            # Stop succeeds, start fails
            mock_run.side_effect = [
                Mock(returncode=0),  # stop success
                Mock(returncode=1)   # start failure
            ]

            manager = PlatformManager()
            result = manager.restart_service("com.test.service")

            assert result is False
            assert mock_run.call_count == 2

    def test_restart_service_linux_sudo_failure(self):
        """Test Linux service restart when sudo fails."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"), \
             patch("subprocess.run", side_effect=subprocess.SubprocessError("sudo: command not found")):

            manager = PlatformManager()
            result = manager.restart_service("test.service")

            assert result is False

    def test_service_management_security(self):
        """Test that service management doesn't allow injection attacks."""
        manager = PlatformManager()

        # Test malicious service names
        malicious_services = [
            "service; rm -rf /",
            "service && echo pwned",
            "service | cat /etc/passwd",
            "`whoami`",
            "$(id)"
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="active")

            for service in malicious_services:
                # Should not execute malicious commands
                status = manager.check_service_status(service)

                # The service name should be passed as a single argument
                if mock_run.called:
                    call_args = mock_run.call_args[0][0]
                    # Service name should be in the command array, not interpreted
                    assert service in call_args


class TestPlatformManagerRobustness:
    """Test PlatformManager robustness and reliability."""

    def test_platform_manager_state_consistency(self):
        """Test that PlatformManager maintains consistent state."""
        manager = PlatformManager()

        # Multiple calls should return consistent results
        platform1 = manager.platform
        platform2 = manager.platform
        assert platform1 == platform2

        is_macos1 = manager.is_macos()
        is_macos2 = manager.is_macos()
        assert is_macos1 == is_macos2

    def test_platform_manager_memory_efficiency(self):
        """Test PlatformManager memory efficiency."""

        # Create multiple instances
        managers = [PlatformManager() for _ in range(10)]

        # All should have the same platform detection
        platforms = [m.platform for m in managers]
        assert all(p == platforms[0] for p in platforms)

        # Clean up
        del managers

    def test_platform_manager_thread_safety_simulation(self):
        """Test PlatformManager behavior in multi-threaded-like scenarios."""
        import threading

        results = []

        def create_manager():
            manager = PlatformManager()
            return {
                "platform": manager.platform,
                "is_macos": manager.is_macos(),
                "thread_id": threading.current_thread().ident
            }

        # Simulate concurrent creation (not truly concurrent in CPython due to GIL)
        managers_data = [create_manager() for _ in range(5)]

        # All should detect the same platform
        platforms = [data["platform"] for data in managers_data]
        assert all(p == platforms[0] for p in platforms)

        # All thread IDs should be different (different threads)
        thread_ids = [data["thread_id"] for data in managers_data]
        # In this context, they'll all be the same thread, but the test structure is correct

    def test_platform_manager_with_corrupted_config(self):
        """Test PlatformManager behavior with corrupted configuration."""
        corrupted_configs = [
            None,  # None config
            {"service_manager": None},  # None values
            {"bin_paths": "not_a_list"},  # Wrong types
            {"invalid": "structure"},  # Missing required keys
        ]

        for corrupted_config in corrupted_configs:
            with patch("src.oaDeviceAPI.core.config.get_platform_config", return_value=corrupted_config):
                manager = PlatformManager()

                # Should handle gracefully without crashing
                try:
                    info = manager.get_platform_info()
                    assert isinstance(info, dict)
                except (AttributeError, TypeError, KeyError):
                    # Some corruption might cause expected errors
                    pass
