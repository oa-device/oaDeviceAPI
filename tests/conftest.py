"""Pytest configuration and fixtures for oaDeviceAPI tests."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_macos_platform():
    """Mock macOS platform detection."""
    with patch("src.oaDeviceAPI.core.config.detect_platform", return_value="macos"):
        yield


@pytest.fixture  
def mock_orangepi_platform():
    """Mock OrangePi platform detection."""
    with patch("src.oaDeviceAPI.core.config.detect_platform", return_value="orangepi"):
        yield


@pytest.fixture
def mock_generic_platform():
    """Mock generic Linux platform detection.""" 
    with patch("src.oaDeviceAPI.core.config.detect_platform", return_value="linux"):
        yield


@pytest.fixture
def mock_psutil():
    """Mock psutil for system metrics."""
    with patch("psutil.cpu_percent", return_value=25.5), \
         patch("psutil.virtual_memory") as mock_mem, \
         patch("psutil.disk_usage") as mock_disk, \
         patch("psutil.net_io_counters") as mock_net:
        
        # Configure mocks
        mock_mem.return_value = Mock(
            percent=45.2, 
            total=8589934592,
            used=3885481984,
            available=4704452608
        )
        
        mock_disk.return_value = Mock(
            percent=67.8,
            total=499963174912, 
            used=338973696512,
            free=160989478400
        )
        
        mock_net.return_value = Mock(
            bytes_sent=1024000,
            bytes_recv=2048000,
            packets_sent=500,
            packets_recv=750
        )
        
        yield


@pytest.fixture
def mock_service_checks():
    """Mock service status checks."""
    with patch("subprocess.run") as mock_run:
        # Default to services running
        mock_run.return_value = Mock(returncode=0, stdout="active")
        yield mock_run


@pytest.fixture
def test_client_macos(mock_macos_platform, mock_psutil, mock_service_checks):
    """Test client with mocked macOS platform."""
    # Import after mocking to ensure platform detection works
    from main import app
    return TestClient(app)


@pytest.fixture
def test_client_orangepi(mock_orangepi_platform, mock_psutil, mock_service_checks):
    """Test client with mocked OrangePi platform."""
    from main import app  
    return TestClient(app)


@pytest.fixture
def sample_health_data():
    """Sample health data for testing."""
    return {
        "cpu": {
            "usage_percent": 25.5,
            "cores": 8,
            "architecture": "arm64"
        },
        "memory": {
            "usage_percent": 45.2,
            "total": 8589934592,
            "used": 3885481984,
            "available": 4704452608
        },
        "disk": {
            "usage_percent": 67.8,
            "total": 499963174912,
            "used": 338973696512, 
            "free": 160989478400,
            "path": "/"
        },
        "network": {
            "bytes_sent": 1024000,
            "bytes_received": 2048000,
            "packets_sent": 500,
            "packets_received": 750
        }
    }


@pytest.fixture
def sample_device_info():
    """Sample device information for testing."""
    return {
        "macos": {
            "type": "Mac",
            "series": "Mac Mini",
            "hostname": "mac-mini-001",
            "model": "Mac14,3"
        },
        "orangepi": {
            "type": "OrangePi",
            "series": "OrangePi 5B", 
            "hostname": "orangepi-001",
            "model": "OrangePi 5B"
        }
    }