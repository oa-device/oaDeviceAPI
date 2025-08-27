"""Pytest configuration and fixtures for oaDeviceAPI tests."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_macos_platform():
    """Mock macOS platform detection."""
    with patch("src.oaDeviceAPI.core.config.detect_platform", return_value="macos"), \
         patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
        yield


@pytest.fixture  
def mock_orangepi_platform():
    """Mock OrangePi platform detection."""
    with patch("src.oaDeviceAPI.core.config.detect_platform", return_value="orangepi"), \
         patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"):
        yield


@pytest.fixture
def mock_generic_platform():
    """Mock generic Linux platform detection.""" 
    with patch("src.oaDeviceAPI.core.config.detect_platform", return_value="linux"), \
         patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "linux"):
        yield


@pytest.fixture
def mock_psutil():
    """Mock psutil for system metrics."""
    with patch("psutil.cpu_percent", return_value=25.5), \
         patch("psutil.virtual_memory") as mock_mem, \
         patch("psutil.disk_usage") as mock_disk, \
         patch("psutil.net_io_counters") as mock_net, \
         patch("psutil.cpu_count", return_value=8), \
         patch("psutil.boot_time", return_value=1640995200.0):
        
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
    with patch("subprocess.run") as mock_run, \
         patch("subprocess.getoutput", return_value="501"):
        # Default to services running
        mock_run.return_value = Mock(returncode=0, stdout="active")
        yield mock_run


@pytest.fixture
def mock_system_commands():
    """Mock system command executions."""
    with patch("subprocess.run") as mock_run, \
         patch("socket.gethostname", return_value="test-device"), \
         patch("platform.platform", return_value="Test-Platform"), \
         patch("platform.machine", return_value="arm64"):
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Test kernel version",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_external_services():
    """Mock external service calls (tracker, camguard)."""
    async def mock_response_json():
        return {
            "detections": 5,
            "fps": 15.2,
            "healthy": True,
            "model_name": "yolo11m.pt"
        }
    
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = mock_response_json
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response
        yield mock_get


@pytest.fixture
def test_client_macos(mock_macos_platform, mock_psutil, mock_service_checks, mock_system_commands):
    """Test client with mocked macOS platform.""" 
    # Clear module cache to ensure fresh imports with mocked platform
    modules_to_clear = [m for m in sys.modules.keys() if m.startswith("main") or m.startswith("src.oaDeviceAPI")]
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    # Import after mocking to ensure platform detection works
    from main import app
    return TestClient(app)


@pytest.fixture
def test_client_orangepi(mock_orangepi_platform, mock_psutil, mock_service_checks, mock_system_commands):
    """Test client with mocked OrangePi platform."""
    # Clear module cache to ensure fresh imports with mocked platform  
    modules_to_clear = [m for m in sys.modules.keys() if m.startswith("main") or m.startswith("src.oaDeviceAPI")]
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
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


@pytest.fixture
def sample_tracker_data():
    """Sample tracker data for testing."""
    return {
        "healthy": True,
        "service_status": "active",
        "detections": 5,
        "fps": 15.2,
        "model_name": "yolo11m.pt",
        "confidence_threshold": 0.5,
        "last_detection": "2024-08-26T10:30:00Z"
    }


@pytest.fixture
def sample_camguard_data():
    """Sample camguard data for testing."""
    return {
        "healthy": True,
        "recording": True,
        "stream_url": "rtsp://localhost:8554/stream",
        "storage_used": 1024000000,  # 1GB
        "recordings_count": 15,
        "last_recording": "2024-08-26T10:25:00Z"
    }


@pytest.fixture
def sample_player_data():
    """Sample player data for testing (OrangePi)."""
    return {
        "healthy": True,
        "service_status": "active",
        "running": True,
        "current_image": "/home/orangead/images/slide001.jpg",
        "images_count": 50,
        "slide_duration": 10,
        "display_connected": True
    }


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.read_text", return_value='{"test": "config"}'), \
         patch("pathlib.Path.write_text"), \
         patch("pathlib.Path.stat") as mock_stat:
        
        # Mock file stats
        mock_stat.return_value = Mock(
            st_size=1024000,
            st_mtime=1640995200.0,
            st_atime=1640995200.0,
            st_ctime=1640995200.0
        )
        
        yield


@pytest.fixture
def mock_network_services():
    """Mock network service dependencies."""
    with patch("socket.gethostname", return_value="test-device"), \
         patch("socket.getfqdn", return_value="test-device.local"), \
         patch("psutil.net_if_addrs") as mock_addrs, \
         patch("psutil.net_if_stats") as mock_stats:
        
        # Mock network interface data
        mock_addrs.return_value = {
            "en0": [Mock(family=2, address="192.168.1.100")],
            "lo0": [Mock(family=2, address="127.0.0.1")]
        }
        
        mock_stats.return_value = {
            "en0": Mock(isup=True, speed=1000),
            "lo0": Mock(isup=True, speed=0)
        }
        
        yield


@pytest.fixture
def mock_temperature_sensors():
    """Mock temperature sensor readings.""" 
    with patch("subprocess.run") as mock_temp_run:
        # Mock temperature command output
        mock_temp_run.return_value = Mock(
            returncode=0,
            stdout="45.2"  # 45.2°C
        )
        yield mock_temp_run


@pytest.fixture
def performance_test_env():
    """Environment setup for performance testing."""
    # Mock all external dependencies for consistent performance testing
    with patch("psutil.cpu_percent", return_value=25.0), \
         patch("psutil.virtual_memory") as mock_mem, \
         patch("psutil.disk_usage") as mock_disk, \
         patch("subprocess.run") as mock_run:
        
        # Fast mock responses
        mock_mem.return_value = Mock(percent=30.0, total=8000000000, used=2400000000, available=5600000000)
        mock_disk.return_value = Mock(percent=40.0, total=500000000000, used=200000000000, free=300000000000)
        mock_run.return_value = Mock(returncode=0, stdout="fast_response")
        
        yield


@pytest.fixture(scope="session")
def test_data_directory():
    """Create temporary directory for test data."""
    import tempfile
    import shutil
    
    temp_dir = Path(tempfile.mkdtemp(prefix="oaDeviceAPI_test_"))
    
    # Create subdirectories
    (temp_dir / "screenshots").mkdir(exist_ok=True)
    (temp_dir / "configs").mkdir(exist_ok=True)
    (temp_dir / "logs").mkdir(exist_ok=True)
    
    yield temp_dir
    
    # Cleanup after tests
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def error_simulation():
    """Fixture for simulating various error conditions."""
    class ErrorSimulator:
        def __init__(self):
            self.active_patches = []
        
        def simulate_service_down(self, service_name):
            """Simulate a service being down."""
            if service_name == "tracker":
                patch_obj = patch("aiohttp.ClientSession.get", 
                                side_effect=ConnectionRefusedError("Service down"))
            elif service_name == "system_commands":
                patch_obj = patch("subprocess.run", 
                                side_effect=FileNotFoundError("Command not found"))
            elif service_name == "psutil":
                patch_obj = patch("psutil.cpu_percent", 
                                side_effect=Exception("System monitoring failed"))
            else:
                patch_obj = patch("subprocess.run", 
                                side_effect=subprocess.SubprocessError("Service error"))
            
            patch_obj.start()
            self.active_patches.append(patch_obj)
            return patch_obj
        
        def cleanup(self):
            """Clean up all active patches."""
            for patch_obj in self.active_patches:
                patch_obj.stop()
            self.active_patches = []
    
    simulator = ErrorSimulator()
    yield simulator
    simulator.cleanup()


@pytest.fixture
def security_test_env():
    """Environment setup for security testing."""
    # Mock external commands to prevent actual execution during security tests
    with patch("subprocess.run") as mock_run, \
         patch("os.system") as mock_system, \
         patch("os.popen") as mock_popen:
        
        # Safe mock responses
        mock_run.return_value = Mock(returncode=0, stdout="safe_output", stderr="")
        mock_system.return_value = 0
        mock_popen.return_value = Mock(read=lambda: "safe_output")
        
        yield {
            "subprocess_run": mock_run,
            "os_system": mock_system, 
            "os_popen": mock_popen
        }


@pytest.fixture
def load_test_env():
    """Environment setup for load testing."""
    # Optimize mocks for load testing
    fast_mocks = {
        "cpu_percent": 25.0,
        "memory_percent": 30.0,
        "disk_percent": 40.0,
        "service_active": True
    }
    
    with patch("psutil.cpu_percent", return_value=fast_mocks["cpu_percent"]), \
         patch("psutil.virtual_memory") as mock_mem, \
         patch("subprocess.run") as mock_run:
        
        # Fast, consistent responses
        mock_mem.return_value = Mock(
            percent=fast_mocks["memory_percent"],
            total=8000000000,
            used=2400000000,
            available=5600000000
        )
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="active" if fast_mocks["service_active"] else "inactive"
        )
        
        yield fast_mocks


@pytest.fixture
def integration_test_env(mock_psutil, mock_service_checks, mock_system_commands, mock_external_services):
    """Comprehensive environment for integration testing."""
    # Combine all necessary mocks for integration tests
    yield {
        "psutil_mocked": True,
        "services_mocked": True,
        "system_commands_mocked": True,
        "external_services_mocked": True
    }


@pytest.fixture
def platform_switching():
    """Fixture to help switch between platform contexts in tests.""" 
    class PlatformSwitcher:
        def __init__(self):
            self.current_patches = []
        
        def switch_to_macos(self):
            """Switch to macOS platform context."""
            self.cleanup()
            
            patches = [
                patch("src.oaDeviceAPI.core.config.detect_platform", return_value="macos"),
                patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"),
                patch("platform.system", return_value="Darwin")
            ]
            
            for p in patches:
                p.start()
                self.current_patches.append(p)
        
        def switch_to_orangepi(self):
            """Switch to OrangePi platform context."""
            self.cleanup()
            
            patches = [
                patch("src.oaDeviceAPI.core.config.detect_platform", return_value="orangepi"),
                patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"),
                patch("platform.system", return_value="Linux")
            ]
            
            for p in patches:
                p.start()
                self.current_patches.append(p)
        
        def cleanup(self):
            """Clean up current patches."""
            for patch_obj in self.current_patches:
                patch_obj.stop()
            self.current_patches = []
    
    switcher = PlatformSwitcher()
    yield switcher
    switcher.cleanup()


# Performance test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", 
        "performance: marks tests as performance tests (may be slow)"
    )
    config.addinivalue_line(
        "markers",
        "security: marks tests as security-focused tests"
    )
    config.addinivalue_line(
        "markers",
        "load: marks tests as load/stress tests"
    )


# Mock data generators
@pytest.fixture
def generate_test_data():
    """Generate various test data scenarios."""
    class TestDataGenerator:
        @staticmethod
        def health_data(cpu_percent=25.0, memory_percent=30.0, disk_percent=40.0):
            return {
                "cpu": {"usage_percent": cpu_percent, "cores": 8},
                "memory": {"usage_percent": memory_percent, "total": 8000000000},
                "disk": {"usage_percent": disk_percent, "total": 500000000000},
                "network": {"bytes_sent": 1000000, "bytes_received": 2000000}
            }
        
        @staticmethod
        def device_info(platform="macos", hostname="test-device"):
            if platform == "macos":
                return {
                    "type": "Mac",
                    "series": "Mac Mini",
                    "hostname": hostname,
                    "model": "Mac14,3"
                }
            else:  # orangepi
                return {
                    "type": "OrangePi", 
                    "series": "OrangePi 5B",
                    "hostname": hostname,
                    "model": "Orange Pi 5B"
                }
        
        @staticmethod
        def service_status(healthy=True, status="active"):
            return {
                "healthy": healthy,
                "service_status": status,
                "running": healthy
            }
    
    return TestDataGenerator()


# Test isolation fixture
@pytest.fixture(autouse=True)
def test_isolation():
    """Ensure test isolation by clearing caches and state."""
    # Clear any global state that might affect tests
    yield
    
    # Cleanup after each test
    import gc
    gc.collect()


# Skip markers for incomplete implementations
def pytest_collection_modifyitems(config, items):
    """Modify collected test items to add skip markers for known issues.""" 
    # Skip tests that require services not yet implemented
    skip_missing_services = pytest.mark.skip(reason="Service implementation pending")
    
    for item in items:
        # Skip tests for services that may not be fully implemented yet
        if "camguard" in item.name and "test_" in item.name:
            # Only skip if the test is expected to fail due to missing implementation
            pass
            
        # Skip performance tests in CI/automated environments unless specifically requested
        if "performance" in item.keywords:
            if not config.getoption("--run-performance", default=False):
                item.add_marker(pytest.mark.skip(reason="Performance tests skipped (use --run-performance)"))


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-performance",
        action="store_true", 
        default=False,
        help="Run performance tests (may be slow)"
    )
    parser.addoption(
        "--run-security",
        action="store_true",
        default=False, 
        help="Run security tests (may attempt various attacks)"
    )
    parser.addoption(
        "--run-load",
        action="store_true",
        default=False,
        help="Run load tests (may be resource intensive)"
    )