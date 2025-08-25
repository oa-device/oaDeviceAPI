"""Unit tests for health schemas and data validation."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.oaDeviceAPI.models.health_schemas import (
    BaseCPUMetrics,
    BaseMemoryMetrics,
    BaseDiskMetrics,
    BaseNetworkMetrics,
    BaseHealthMetrics,
    BaseSystemInfo,
    BaseDeviceInfo,
    BaseVersionInfo,
    MacOSCapabilities,
    OrangePiCapabilities,
    MacOSHealthResponse,
    OrangePiHealthResponse,
    StandardizedErrorResponse,
)


class TestBasicMetrics:
    """Test basic metric schemas."""
    
    def test_cpu_metrics_valid(self):
        """Test valid CPU metrics."""
        cpu = BaseCPUMetrics(
            usage_percent=25.5,
            cores=8,
            architecture="arm64",
            model="Apple M2"
        )
        assert cpu.usage_percent == 25.5
        assert cpu.cores == 8
        assert cpu.architecture == "arm64"
        assert cpu.model == "Apple M2"
    
    def test_cpu_metrics_required_fields(self):
        """Test CPU metrics with only required fields."""
        cpu = BaseCPUMetrics(usage_percent=50.0, cores=4)
        assert cpu.usage_percent == 50.0
        assert cpu.cores == 4
        assert cpu.architecture is None
        assert cpu.model is None
    
    def test_cpu_metrics_validation_error(self):
        """Test CPU metrics validation errors."""
        with pytest.raises(ValidationError):
            BaseCPUMetrics(usage_percent="invalid", cores=4)
        
        with pytest.raises(ValidationError):
            BaseCPUMetrics(usage_percent=25.5)  # Missing required cores
    
    def test_memory_metrics_valid(self):
        """Test valid memory metrics."""
        memory = BaseMemoryMetrics(
            usage_percent=45.2,
            total=8589934592,
            used=3885481984,
            available=4704452608
        )
        assert memory.usage_percent == 45.2
        assert memory.total == 8589934592
        assert memory.used == 3885481984
        assert memory.available == 4704452608
    
    def test_disk_metrics_with_path(self):
        """Test disk metrics with custom path."""
        disk = BaseDiskMetrics(
            usage_percent=67.8,
            total=499963174912,
            used=338973696512,
            free=160989478400,
            path="/home"
        )
        assert disk.path == "/home"
    
    def test_network_metrics_complete(self):
        """Test complete network metrics."""
        network = BaseNetworkMetrics(
            bytes_sent=1024000,
            bytes_received=2048000,
            packets_sent=500,
            packets_received=750,
            interface="en0"
        )
        assert network.interface == "en0"


class TestCapabilities:
    """Test platform-specific capabilities."""
    
    def test_macos_capabilities(self):
        """Test macOS capabilities."""
        caps = MacOSCapabilities(
            supports_camera_stream=True,
            supports_tracker_restart=True,
            device_has_camera_support=True
        )
        assert caps.supports_camera_stream is True
        assert caps.supports_tracker_restart is True
        assert caps.device_has_camera_support is True
        assert caps.supports_reboot is True  # Inherited from base
    
    def test_orangepi_capabilities(self):
        """Test OrangePi capabilities."""
        caps = OrangePiCapabilities(
            supports_screenshots=True,
            supports_player_restart=True,
            supports_display_setup=True,
            device_has_camera_support=False
        )
        assert caps.supports_screenshots is True
        assert caps.supports_player_restart is True
        assert caps.supports_display_setup is True
        assert caps.device_has_camera_support is False
        assert caps.supports_reboot is True  # Inherited from base


class TestHealthResponses:
    """Test complete health response schemas."""
    
    def test_macos_health_response(self, sample_health_data, sample_device_info):
        """Test macOS health response structure."""
        response = MacOSHealthResponse(
            status="online",
            hostname="mac-mini-001",
            timestamp=datetime.now().isoformat(),
            timestamp_epoch=int(datetime.now().timestamp()),
            version=BaseVersionInfo(
                api="1.0.0",
                python="3.12.0",
                system={"os": "macOS", "version": "14.0"}
            ),
            metrics=BaseHealthMetrics(**sample_health_data),
            device_info=BaseDeviceInfo(**sample_device_info["macos"]),
            capabilities=MacOSCapabilities(),
            system=BaseSystemInfo(
                os_version="macOS 14.0",
                hostname="mac-mini-001",
                uptime=86400.0,
                uptime_human="1 day"
            )
        )
        
        assert response.status == "online"
        assert response.hostname == "mac-mini-001"
        assert isinstance(response.capabilities, MacOSCapabilities)
        assert response.capabilities.supports_camera_stream is True
    
    def test_orangepi_health_response(self, sample_health_data, sample_device_info):
        """Test OrangePi health response structure."""
        response = OrangePiHealthResponse(
            status="online", 
            hostname="orangepi-001",
            timestamp=datetime.now().isoformat(),
            timestamp_epoch=int(datetime.now().timestamp()),
            version=BaseVersionInfo(
                api="1.0.0",
                python="3.12.0",
                system={"os": "Ubuntu", "version": "22.04"}
            ),
            metrics=BaseHealthMetrics(**sample_health_data),
            device_info=BaseDeviceInfo(**sample_device_info["orangepi"]),
            capabilities=OrangePiCapabilities()
        )
        
        assert response.status == "online"
        assert response.hostname == "orangepi-001"
        assert isinstance(response.capabilities, OrangePiCapabilities)
        assert response.capabilities.supports_screenshots is True


class TestErrorResponses:
    """Test error response schemas."""
    
    def test_standardized_error_response(self):
        """Test standardized error response."""
        error = StandardizedErrorResponse(
            timestamp=datetime.now().isoformat(),
            timestamp_epoch=int(datetime.now().timestamp()),
            error="Test error message"
        )
        
        assert error.status == "error"
        assert error.error == "Test error message"
        assert error.timestamp is not None
        assert error.timestamp_epoch > 0


class TestSchemaCompatibility:
    """Test schema compatibility and extensibility."""
    
    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed in base schemas."""
        cpu = BaseCPUMetrics(
            usage_percent=25.0,
            cores=4,
            temperature=45.5,  # Extra field
            frequency=2400      # Extra field
        )
        
        # Extra fields should be preserved
        assert hasattr(cpu, 'temperature')
        assert cpu.temperature == 45.5  # type: ignore
    
    def test_schema_serialization(self, sample_health_data):
        """Test schema serialization to dict."""
        metrics = BaseHealthMetrics(**sample_health_data)
        data_dict = metrics.model_dump()
        
        required_keys = ["cpu", "memory", "disk", "network"]
        for key in required_keys:
            assert key in data_dict
        
        # Should be able to recreate from dict
        recreated = BaseHealthMetrics(**data_dict)
        assert recreated.cpu.usage_percent == metrics.cpu.usage_percent
    
    def test_cross_platform_compatibility(self, sample_health_data, sample_device_info):
        """Test that base schemas work across platforms."""
        # Same metrics should work for both platforms
        macos_response = MacOSHealthResponse(
            status="online",
            hostname="test-mac", 
            timestamp=datetime.now().isoformat(),
            timestamp_epoch=int(datetime.now().timestamp()),
            version=BaseVersionInfo(api="1.0.0", python="3.12.0", system={}),
            metrics=BaseHealthMetrics(**sample_health_data),
            device_info=BaseDeviceInfo(**sample_device_info["macos"]),
            capabilities=MacOSCapabilities(),
            system=BaseSystemInfo(os_version="macOS", hostname="test-mac")
        )
        
        orangepi_response = OrangePiHealthResponse(
            status="online",
            hostname="test-orangepi",
            timestamp=datetime.now().isoformat(), 
            timestamp_epoch=int(datetime.now().timestamp()),
            version=BaseVersionInfo(api="1.0.0", python="3.12.0", system={}),
            metrics=BaseHealthMetrics(**sample_health_data),
            device_info=BaseDeviceInfo(**sample_device_info["orangepi"]),
            capabilities=OrangePiCapabilities()
        )
        
        # Both should have same base structure
        assert macos_response.metrics.cpu.usage_percent == orangepi_response.metrics.cpu.usage_percent
        assert macos_response.status == orangepi_response.status