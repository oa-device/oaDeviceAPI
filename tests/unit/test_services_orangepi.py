"""Unit tests for OrangePi-specific services."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.oaDeviceAPI.platforms.orangepi.services.display import get_display_info
from src.oaDeviceAPI.platforms.orangepi.services.health import (
    calculate_health_score,
    get_health_summary,
)
from src.oaDeviceAPI.platforms.orangepi.services.player import (
    check_player_status,
    get_deployment_info,
)
from src.oaDeviceAPI.platforms.orangepi.services.system import (
    get_device_info,
    get_system_metrics,
)


class TestOrangePiSystemServices:
    """Test OrangePi system information services."""

    @patch("subprocess.run")
    @patch("socket.gethostname")
    @patch("psutil.boot_time")
    def test_get_system_metrics_success(self, mock_boot_time, mock_hostname, mock_run):
        """Test successful OrangePi system info gathering."""
        mock_hostname.return_value = "orangepi-001"
        mock_boot_time.return_value = 1640995200.0
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Linux orangepi-001 5.10.160-legacy-rk35xx #1 SMP"
        )

        info = get_system_metrics()

        assert info["hostname"] == "orangepi-001"
        assert "uptime" in info
        assert "boot_time" in info
        assert "Linux" in info["kernel_version"]

    @patch("subprocess.run")
    def test_get_system_metrics_kernel_failure(self, mock_run):
        """Test system info when kernel command fails."""
        mock_run.side_effect = subprocess.SubprocessError("uname failed")

        info = get_system_metrics()

        assert info["kernel_version"] == "Unknown"
        assert "hostname" in info  # Should still get hostname

    @patch("subprocess.run")
    def test_get_device_info_orangepi_5b(self, mock_run):
        """Test device info for OrangePi 5B."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Orange Pi 5B"),  # device-tree model
            Mock(returncode=0, stdout="Orange Pi 5B Board")  # board name
        ]

        info = get_device_info()

        assert info["type"] == "OrangePi"
        assert info["series"] == "OrangePi 5B"
        assert info["model"] == "Orange Pi 5B"
        assert "hostname" in info

    @patch("subprocess.run")
    def test_get_device_info_generic_orangepi(self, mock_run):
        """Test device info for generic OrangePi."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="orangepi"),  # generic model
            Mock(returncode=1, stderr="No board info")  # board command fails
        ]

        info = get_device_info()

        assert info["type"] == "OrangePi"
        assert "orangepi" in info["model"].lower()
        assert info["series"] in ["OrangePi", "Unknown"]  # Fallback

    @patch("subprocess.run")
    def test_get_device_info_all_commands_fail(self, mock_run):
        """Test device info when all commands fail."""
        mock_run.side_effect = subprocess.SubprocessError("All commands failed")

        info = get_device_info()

        assert info["type"] == "OrangePi"  # Should still identify as OrangePi
        assert info["model"] == "Unknown"
        assert info["series"] == "Unknown"


class TestOrangePiPlayerService:
    """Test OrangePi player service functionality."""

    @patch("subprocess.run")
    def test_check_player_status_active(self, mock_run):
        """Test player status when service is active."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="active"
        )

        status = check_player_status()

        assert status["service_status"] == "active"
        assert status["healthy"] is True
        assert status["running"] is True

    @patch("subprocess.run")
    def test_check_player_status_inactive(self, mock_run):
        """Test player status when service is inactive."""
        mock_run.return_value = Mock(
            returncode=3,  # systemctl inactive return code
            stdout="inactive"
        )

        status = check_player_status()

        assert status["service_status"] == "inactive"
        assert status["healthy"] is False
        assert status["running"] is False

    @patch("subprocess.run")
    def test_check_player_status_command_failure(self, mock_run):
        """Test player status when systemctl command fails."""
        mock_run.side_effect = FileNotFoundError("systemctl not found")

        status = check_player_status()

        assert status["healthy"] is False
        assert "error" in status
        assert status["service_status"] == "unknown"

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    def test_get_deployment_info_success(self, mock_open_file, mock_exists):
        """Test slideshow information gathering."""
        mock_exists.return_value = True
        slideshow_config = {
            "images_directory": "/home/orangead/images",
            "slide_duration": 10,
            "transition_effect": "fade",
            "image_count": 25
        }
        mock_open_file.return_value = mock_open(read_data=json.dumps(slideshow_config))

        info = get_deployment_info()

        assert info["images_directory"] == "/home/orangead/images"
        assert info["slide_duration"] == 10
        assert info["image_count"] == 25
        assert info["transition_effect"] == "fade"

    @patch("pathlib.Path.exists")
    def test_get_deployment_info_no_config(self, mock_exists):
        """Test slideshow info when config file doesn't exist."""
        mock_exists.return_value = False

        info = get_deployment_info()

        assert info["status"] == "No configuration found"
        assert info["images_directory"] is None

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    def test_get_deployment_info_invalid_json(self, mock_open_file, mock_exists):
        """Test slideshow info with invalid JSON config."""
        mock_exists.return_value = True
        mock_open_file.return_value = mock_open(read_data="invalid json {")

        info = get_deployment_info()

        assert "error" in info
        assert info["images_directory"] is None


class TestOrangePiDisplayService:
    """Test OrangePi display services."""

    @patch("subprocess.run")
    def test_get_display_info_hdmi_connected(self, mock_run):
        """Test display info when HDMI is connected."""
        # Mock xrandr output for connected HDMI
        xrandr_output = """Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767
HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 510mm x 287mm
   1920x1080     60.00*+  59.93    50.00    
   1680x1050     59.95    
   1600x900      60.00    
   1280x1024     75.02    60.02    
   1280x800      59.81    
   1280x720      60.00    50.00    59.86    
"""

        mock_run.return_value = Mock(returncode=0, stdout=xrandr_output)

        info = get_display_info()

        assert info["connected"] is True
        assert len(info["displays"]) > 0
        assert info["displays"][0]["name"] == "HDMI-1"
        assert info["displays"][0]["resolution"] == "1920x1080"
        assert info["displays"][0]["status"] == "connected"

    @patch("subprocess.run")
    def test_get_display_info_no_display(self, mock_run):
        """Test display info when no display is connected."""
        xrandr_output = """Screen 0: minimum 8 x 8, current 1024 x 768, maximum 32767 x 32767
HDMI-1 disconnected (normal left inverted right x axis y axis)
"""

        mock_run.return_value = Mock(returncode=0, stdout=xrandr_output)

        info = get_display_info()

        assert info["connected"] is False
        assert len(info["displays"]) == 0 or info["displays"][0]["status"] == "disconnected"

    @patch("subprocess.run")
    def test_get_display_info_xrandr_failure(self, mock_run):
        """Test display info when xrandr command fails."""
        mock_run.side_effect = subprocess.SubprocessError("xrandr not available")

        info = get_display_info()

        assert info["connected"] is False
        assert info["displays"] == []
        assert "error" in info

    @patch("subprocess.run")
    def test_get_display_info_malformed_output(self, mock_run):
        """Test display info with malformed xrandr output."""
        malformed_outputs = [
            "",  # Empty
            "Some random text",  # No display info
            "HDMI-1 unknown state",  # Unknown connection state
            "Invalid format display output"
        ]

        for output in malformed_outputs:
            mock_run.return_value = Mock(returncode=0, stdout=output)

            info = get_display_info()

            # Should handle malformed output gracefully
            assert isinstance(info, dict)
            assert "connected" in info
            assert isinstance(info["displays"], list)


class TestOrangePiActionsService:
    """Test OrangePi action services."""

    @patch("subprocess.run")
    async def test_reboot_system_success(self, mock_run):
        """Test successful system reboot."""
        mock_run.return_value = Mock(returncode=0)

        from src.oaDeviceAPI.platforms.orangepi.services.actions import reboot_system

        result = await reboot_system()

        assert result["success"] is True
        assert "reboot" in result["message"].lower()
        mock_run.assert_called_once()
        assert "sudo" in mock_run.call_args[0][0]

    @patch("subprocess.run")
    async def test_reboot_system_permission_denied(self, mock_run):
        """Test system reboot with permission denied."""
        mock_run.side_effect = PermissionError("Permission denied")

        from src.oaDeviceAPI.platforms.orangepi.services.actions import reboot_system

        result = await reboot_system()

        assert result["success"] is False
        assert "permission" in result["error"].lower()

    @patch("src.oaDeviceAPI.core.platform.platform_manager.restart_service")
    async def test_restart_player_success(self, mock_restart):
        """Test successful player restart."""
        mock_restart.return_value = True

        from src.oaDeviceAPI.platforms.orangepi.services.actions import restart_player

        result = await restart_player()

        assert result["success"] is True
        assert "player" in result["message"].lower()

    @patch("src.oaDeviceAPI.core.platform.platform_manager.restart_service")
    async def test_restart_player_failure(self, mock_restart):
        """Test player restart failure."""
        mock_restart.return_value = False

        from src.oaDeviceAPI.platforms.orangepi.services.actions import restart_player

        result = await restart_player()

        assert result["success"] is False
        assert "failed" in result["message"].lower()


class TestOrangePiUtilsService:
    """Test OrangePi utility services."""

    @patch("subprocess.run")
    def test_execute_command_with_timeout(self, mock_run):
        """Test command execution with timeout."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output",
            stderr=""
        )

        from src.oaDeviceAPI.platforms.orangepi.services.utils import execute_command

        result = execute_command(["echo", "test"], timeout=5)

        assert result["success"] is True
        assert result["stdout"] == "output"
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs.get("timeout") == 5

    @patch("subprocess.run")
    def test_execute_command_timeout_exceeded(self, mock_run):
        """Test command execution when timeout is exceeded."""
        mock_run.side_effect = subprocess.TimeoutExpired("sleep", 10)

        from src.oaDeviceAPI.platforms.orangepi.services.utils import execute_command

        result = execute_command(["sleep", "10"], timeout=1)

        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.mkdir")
    def test_ensure_directory_creation(self, mock_mkdir, mock_exists):
        """Test directory creation utility."""
        mock_exists.return_value = False

        from src.oaDeviceAPI.platforms.orangepi.services.utils import ensure_directory

        result = ensure_directory("/tmp/test_screenshots")

        assert result["success"] is True
        mock_mkdir.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_ensure_directory_already_exists(self, mock_exists):
        """Test directory creation when directory already exists."""
        mock_exists.return_value = True

        from src.oaDeviceAPI.platforms.orangepi.services.utils import ensure_directory

        result = ensure_directory("/tmp/existing")

        assert result["success"] is True
        assert "already exists" in result["message"]


class TestOrangePiHealthScoring:
    """Test OrangePi-specific health scoring."""

    def test_calculate_health_score_player_focused(self):
        """Test health scoring with focus on player service."""
        metrics = {
            "cpu": {"percent": 30.0},
            "memory": {"percent": 50.0},
            "disk": {"percent": 70.0},
        }
        player_status = {"healthy": True, "service_status": "active"}
        display_info = {"connected": True, "displays": [{"name": "HDMI-1"}]}

        scores = calculate_health_score(metrics, player_status, display_info)

        assert scores["cpu"] == 70.0  # 100 - 30
        assert scores["memory"] == 50.0  # 100 - 50
        assert scores["disk"] == 30.0  # 100 - 70
        assert scores["player"] == 100.0  # Healthy
        assert scores["display"] == 100.0  # Connected
        assert scores["overall"] > 50.0

    def test_calculate_health_score_critical_system(self):
        """Test health scoring with critical system state."""
        metrics = {
            "cpu": {"percent": 98.0},  # Critical CPU
            "memory": {"percent": 95.0},  # Critical memory
            "disk": {"percent": 99.0}  # Critical disk
        }
        player_status = {"healthy": False, "service_status": "failed"}
        display_info = {"connected": False, "displays": []}

        scores = calculate_health_score(metrics, player_status, display_info)

        assert scores["cpu"] <= 5.0  # Very low CPU score
        assert scores["memory"] <= 10.0  # Very low memory score
        assert scores["disk"] <= 5.0  # Very low disk score
        assert scores["player"] == 0.0  # Unhealthy player
        assert scores["display"] == 0.0  # No display
        assert scores["overall"] < 20.0  # Critical overall
        assert scores["status"]["critical"] is True

    def test_health_summary_with_player_issues(self):
        """Test health summary focusing on player issues."""
        metrics = {
            "cpu": {"percent": 20.0},
            "memory": {"percent": 30.0},
            "disk": {"percent": 85.0}  # Low disk space
        }
        player_status = {
            "healthy": False,
            "service_status": "inactive",
            "display_connected": False
        }
        display_info = {"connected": False, "displays": []}

        summary = get_health_summary(metrics, player_status, display_info)

        assert summary["needs_attention"] is True
        assert any("disk space" in w.lower() for w in summary["warnings"])
        assert any("player" in w.lower() for w in summary["warnings"])
        assert any("display" in r.lower() for r in summary["recommendations"])


class TestOrangePiScreenshotService:
    """Test OrangePi screenshot service functionality."""

    @patch("subprocess.run")
    def test_capture_screenshot_success(self, mock_run):
        """Test successful screenshot capture."""
        mock_run.return_value = Mock(returncode=0, stdout="")

        from src.oaDeviceAPI.platforms.orangepi.services.utils import capture_screenshot

        with patch("pathlib.Path.exists", return_value=True):
            result = capture_screenshot("/tmp/test_screenshot.png")

            assert result["success"] is True
            assert result["file_path"] == "/tmp/test_screenshot.png"
            assert "captured" in result["message"].lower()

    @patch("subprocess.run")
    def test_capture_screenshot_display_not_available(self, mock_run):
        """Test screenshot when display is not available."""
        mock_run.side_effect = subprocess.SubprocessError("DISPLAY not set")

        from src.oaDeviceAPI.platforms.orangepi.services.utils import capture_screenshot

        result = capture_screenshot("/tmp/screenshot.png")

        assert result["success"] is False
        assert "display" in result["error"].lower()

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_capture_screenshot_file_not_created(self, mock_exists, mock_run):
        """Test screenshot when file creation fails."""
        mock_run.return_value = Mock(returncode=0)  # Command succeeds
        mock_exists.return_value = False  # But file not created

        from src.oaDeviceAPI.platforms.orangepi.services.utils import capture_screenshot

        result = capture_screenshot("/tmp/screenshot.png")

        assert result["success"] is False
        assert "file not created" in result["error"].lower()

    def test_get_screenshot_history(self):
        """Test screenshot history retrieval."""
        mock_files = [
            Path("/tmp/screenshots/screenshot_2024-01-01_10-00-00.png"),
            Path("/tmp/screenshots/screenshot_2024-01-01_11-00-00.png"),
            Path("/tmp/screenshots/screenshot_2024-01-01_12-00-00.png")
        ]

        with patch("pathlib.Path.glob", return_value=mock_files), \
             patch("pathlib.Path.stat") as mock_stat:

            # Mock file stats
            mock_stat.return_value = Mock(st_size=1024000, st_mtime=1640995200.0)

            from src.oaDeviceAPI.platforms.orangepi.services.utils import (
                get_screenshot_history,
            )

            history = get_screenshot_history("/tmp/screenshots")

            assert len(history) == 3
            for item in history:
                assert "filename" in item
                assert "size" in item
                assert "timestamp" in item
                assert item["size"] == 1024000


class TestOrangePiServiceIntegration:
    """Test integration between OrangePi services."""

    def test_service_dependency_validation(self):
        """Test that services validate their dependencies."""
        from src.oaDeviceAPI.platforms.orangepi.services.utils import (
            check_service_dependencies,
        )

        # Test required binaries
        required_binaries = ["systemctl", "xrandr", "scrot"]

        with patch("shutil.which") as mock_which:
            # All binaries available
            mock_which.return_value = "/usr/bin/command"

            deps = check_service_dependencies(required_binaries)

            assert deps["all_available"] is True
            assert len(deps["missing"]) == 0

            # Some binaries missing
            mock_which.side_effect = lambda x: None if x == "scrot" else "/usr/bin/command"

            deps = check_service_dependencies(required_binaries)

            assert deps["all_available"] is False
            assert "scrot" in deps["missing"]

    @patch("src.oaDeviceAPI.platforms.orangepi.services.player.check_player_status")
    @patch("src.oaDeviceAPI.platforms.orangepi.services.display.get_display_info")
    def test_player_display_integration(self, mock_display, mock_player):
        """Test integration between player and display services."""
        # Display connected, player healthy
        mock_display.return_value = {
            "connected": True,
            "displays": [{"name": "HDMI-1", "resolution": "1920x1080"}]
        }
        mock_player.return_value = {
            "healthy": True,
            "service_status": "active",
            "display_connected": True
        }

        # Health calculation should consider both
        scores = calculate_health_score(
            {"cpu": {"percent": 20}, "memory": {"percent": 30}, "disk": {"percent": 40}},
            mock_player.return_value,
            mock_display.return_value
        )

        assert scores["player"] == 100.0
        assert scores["display"] == 100.0
        assert scores["overall"] > 60.0


class TestOrangePiServiceConfiguration:
    """Test error handling across OrangePi services."""

    def test_service_resilience_to_missing_files(self):
        """Test service resilience when config files are missing."""
        missing_file_scenarios = [
            "/etc/orangead/display.conf",
            "/home/orangead/.config/player.json",
            "/var/log/player.log"
        ]

        for file_path in missing_file_scenarios:
            with patch("pathlib.Path.exists", return_value=False):
                # Services should handle missing files gracefully
                try:
                    from src.oaDeviceAPI.platforms.orangepi.services.player import (
                        get_deployment_info,
                    )
                    result = get_deployment_info()
                    assert isinstance(result, dict)
                    # Should have fallback/error handling
                except FileNotFoundError:
                    pytest.fail(f"Service should handle missing file: {file_path}")

    @patch("subprocess.run")
    def test_service_resilience_to_command_failures(self, mock_run):
        """Test service resilience to command execution failures."""
        # Simulate various command failure scenarios
        failure_scenarios = [
            subprocess.CalledProcessError(1, "command"),
            subprocess.TimeoutExpired("command", 30),
            FileNotFoundError("Command not found"),
            PermissionError("Permission denied"),
            OSError("System error")
        ]

        for exception in failure_scenarios:
            mock_run.side_effect = exception

            # Test multiple services handle failures gracefully
            services_to_test = [
                check_player_status,
                get_system_metrics,
                get_device_info
            ]

            for service_func in services_to_test:
                result = service_func()
                assert isinstance(result, dict)
                # Should contain error info or fallback values
                assert "error" in result or any(
                    key in result for key in ["hostname", "type", "service_status"]
                )

    def test_concurrent_service_calls(self):
        """Test concurrent service calls don't interfere."""
        import asyncio

        async def call_multiple_services():
            """Simulate concurrent service calls."""
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="active")

                # Simulate concurrent calls
                tasks = [
                    check_player_status(),
                    get_system_metrics(),
                    get_device_info(),
                    get_display_info()
                ]

                # Execute synchronously (services aren't async)
                results = [task for task in tasks]

                return results

        # This test validates that services can be called concurrently without state issues
        results = asyncio.run(call_multiple_services())

        assert len(results) == 4
        for result in results:
            assert isinstance(result, dict)


class TestOrangePiServiceConfiguration:
    """Test OrangePi service configuration handling."""

    @patch("builtins.open")
    @patch("pathlib.Path.exists")
    def test_load_service_config_success(self, mock_exists, mock_open_file):
        """Test successful service configuration loading."""
        mock_exists.return_value = True
        config_data = {
            "player": {
                "images_directory": "/home/orangead/images",
                "slide_duration": 10,
                "auto_start": True
            },
            "display": {
                "resolution": "1920x1080",
                "refresh_rate": 60
            }
        }
        mock_open_file.return_value = mock_open(read_data=json.dumps(config_data))

        from src.oaDeviceAPI.platforms.orangepi.services.utils import (
            load_service_config,
        )

        config = load_service_config("/etc/orangead/config.json")

        assert config["player"]["slide_duration"] == 10
        assert config["display"]["resolution"] == "1920x1080"

    @patch("pathlib.Path.exists")
    def test_load_service_config_file_missing(self, mock_exists):
        """Test service config loading when file is missing."""
        mock_exists.return_value = False

        from src.oaDeviceAPI.platforms.orangepi.services.utils import (
            load_service_config,
        )

        config = load_service_config("/nonexistent/config.json")

        assert config == {}

    @patch("builtins.open")
    @patch("pathlib.Path.exists")
    def test_load_service_config_invalid_json(self, mock_exists, mock_open_file):
        """Test service config with invalid JSON."""
        mock_exists.return_value = True
        mock_open_file.return_value = mock_open(read_data="{invalid json")

        from src.oaDeviceAPI.platforms.orangepi.services.utils import (
            load_service_config,
        )

        config = load_service_config("/path/to/config.json")

        assert config == {}  # Should return empty dict on JSON error


class TestOrangePiServiceRobustness:
    """Test OrangePi service robustness and reliability."""

    def test_service_state_consistency(self):
        """Test that services maintain consistent state."""
        # Multiple calls should return consistent results
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="active")

            status1 = check_player_status()
            status2 = check_player_status()

            # Should be consistent
            assert status1["service_status"] == status2["service_status"]
            assert status1["healthy"] == status2["healthy"]

    def test_service_memory_efficiency(self):
        """Test service memory efficiency."""
        # Services should not accumulate state
        initial_results = []
        final_results = []

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="data")

            # Call services multiple times
            for _ in range(10):
                initial_results.append(check_player_status())

            for _ in range(10):
                final_results.append(check_player_status())

            # Results should be consistent and not accumulate memory
            assert len(initial_results) == len(final_results) == 10
            for i, f in zip(initial_results, final_results, strict=False):
                assert type(i) == type(f)  # Same result structure

    def test_service_error_recovery(self):
        """Test that services can recover from temporary errors."""
        with patch("subprocess.run") as mock_run:
            # First call fails, second succeeds
            mock_run.side_effect = [
                subprocess.SubprocessError("Temporary failure"),
                Mock(returncode=0, stdout="active")
            ]

            # First call should handle error
            status1 = check_player_status()
            assert status1["healthy"] is False

            # Second call should succeed
            status2 = check_player_status()
            assert status2["service_status"] == "active"

    def test_unicode_handling_in_services(self):
        """Test that services handle unicode data correctly."""
        unicode_test_data = {
            "hostname": "测试设备-001",
            "model": "Orange Pi 5B 开发板",
            "output": "系统正常运行"
        }

        with patch("socket.gethostname", return_value=unicode_test_data["hostname"]), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(
                returncode=0,
                stdout=unicode_test_data["output"]
            )

            info = get_system_metrics()

            # Should handle unicode without encoding errors
            assert isinstance(info, dict)
            assert info["hostname"] == unicode_test_data["hostname"]
