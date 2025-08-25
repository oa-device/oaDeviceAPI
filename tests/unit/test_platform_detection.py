"""Unit tests for platform detection logic."""

import pytest
from unittest.mock import patch, mock_open
from src.oaDeviceAPI.core.config import detect_platform, get_platform_config
from src.oaDeviceAPI.core.platform import PlatformManager


class TestPlatformDetection:
    """Test platform detection functionality."""
    
    def test_detect_macos_platform(self):
        """Test macOS platform detection."""
        with patch("platform.system", return_value="Darwin"):
            assert detect_platform() == "macos"
    
    def test_detect_orangepi_platform(self):
        """Test OrangePi platform detection via device tree.""" 
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", mock_open(read_data="Orange Pi 5B")):
            assert detect_platform() == "orangepi"
    
    def test_detect_orangepi_via_os_release(self):
        """Test OrangePi platform detection via os-release."""
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", side_effect=[
                 FileNotFoundError,  # No device-tree/model
                 mock_open(read_data="ID=ubuntu\nNAME=Ubuntu")()
             ]):
            assert detect_platform() == "orangepi" 
    
    def test_detect_generic_linux(self):
        """Test generic Linux platform detection."""
        with patch("platform.system", return_value="Linux"), \
             patch("builtins.open", side_effect=FileNotFoundError):
            assert detect_platform() == "linux"
    
    def test_detect_unknown_platform(self):
        """Test unknown platform detection."""
        with patch("platform.system", return_value="Windows"):
            assert detect_platform() == "unknown"
    
    def test_platform_override(self):
        """Test manual platform override."""
        with patch("src.oaDeviceAPI.core.config.Settings") as mock_settings:
            mock_settings.return_value.platform_override = "macos"
            with patch("platform.system", return_value="Linux"):
                # Would normally detect Linux, but override forces macOS
                assert detect_platform() == "macos"


class TestPlatformConfig:
    """Test platform configuration."""
    
    def test_macos_config(self):
        """Test macOS platform configuration."""
        config = get_platform_config() 
        # This will use whatever platform is detected in the test environment
        assert "service_manager" in config
        assert "bin_paths" in config
        assert "temp_dir" in config
    
    def test_platform_specific_features(self):
        """Test platform-specific feature flags."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            config = get_platform_config()
            assert config["camera_supported"] == True
            assert config["tracker_supported"] == True
            assert config["screenshot_supported"] == False
        
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"):
            config = get_platform_config()
            assert config["camera_supported"] == False
            assert config["tracker_supported"] == False  
            assert config["screenshot_supported"] == True


class TestPlatformManager:
    """Test PlatformManager functionality."""
    
    def test_platform_manager_macos(self):
        """Test PlatformManager with macOS."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            manager = PlatformManager()
            assert manager.is_macos() == True
            assert manager.is_orangepi() == False
            assert manager.supports_feature("camera") == True
            assert manager.get_service_manager() == "launchctl"
    
    def test_platform_manager_orangepi(self):
        """Test PlatformManager with OrangePi."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"):
            manager = PlatformManager()
            assert manager.is_macos() == False
            assert manager.is_orangepi() == True
            assert manager.supports_feature("screenshot") == True
            assert manager.get_service_manager() == "systemctl"
    
    def test_get_platform_info(self):
        """Test getting comprehensive platform information."""
        manager = PlatformManager()
        info = manager.get_platform_info()
        
        required_keys = ["platform", "service_manager", "bin_paths", "temp_dir", "features", "config"]
        for key in required_keys:
            assert key in info
        
        assert "screenshot" in info["features"]
        assert "camera" in info["features"] 
        assert "tracker" in info["features"]
        assert "camguard" in info["features"]
    
    def test_service_status_check_macos(self):
        """Test service status check on macOS.""" 
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.getoutput", return_value="501"):
            
            mock_run.return_value.stdout = "state = running"
            manager = PlatformManager()
            
            assert manager.check_service_status("com.test.service") == True
    
    def test_service_status_check_linux(self):
        """Test service status check on Linux."""
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"), \
             patch("subprocess.run") as mock_run:
            
            mock_run.return_value.stdout = "active"
            manager = PlatformManager()
            
            assert manager.check_service_status("test.service") == True