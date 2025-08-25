"""End-to-end deployment scenario tests."""

import pytest
import subprocess
import time
import requests
from pathlib import Path


@pytest.mark.slow
class TestDeploymentScenarios:
    """Test real deployment scenarios."""
    
    @pytest.fixture
    def api_server(self):
        """Start API server for testing."""
        # Start server in background
        process = subprocess.Popen(
            ["python", "main.py"],
            cwd="oaDeviceAPI",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        time.sleep(3)
        
        # Check if server is running
        try:
            response = requests.get("http://localhost:9090/", timeout=5)
            if response.status_code != 200:
                raise Exception("Server failed to start")
        except Exception:
            process.terminate()
            raise
        
        yield process
        
        # Cleanup
        process.terminate()
        process.wait()
    
    def test_api_startup_sequence(self, api_server):
        """Test complete API startup sequence.""" 
        # Test basic connectivity
        response = requests.get("http://localhost:9090/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "running"
        assert "platform" in data
        assert "endpoints" in data
    
    def test_health_monitoring_workflow(self, api_server):
        """Test complete health monitoring workflow."""
        base_url = "http://localhost:9090"
        
        # Get platform info
        platform_response = requests.get(f"{base_url}/platform")
        assert platform_response.status_code == 200
        platform_data = platform_response.json()
        
        # Get health data
        health_response = requests.get(f"{base_url}/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        
        # Validate health data structure
        required_keys = ["status", "metrics", "device_info", "capabilities"]
        for key in required_keys:
            assert key in health_data
        
        # Get health summary
        summary_response = requests.get(f"{base_url}/health/summary")
        assert summary_response.status_code == 200
    
    def test_platform_specific_endpoints(self, api_server):
        """Test platform-specific endpoint availability."""
        base_url = "http://localhost:9090"
        
        # Get available endpoints
        root_response = requests.get(f"{base_url}/")
        endpoints = root_response.json()["endpoints"]
        
        # Test that only appropriate endpoints are available
        if "cameras" in endpoints:
            # Should be macOS
            camera_response = requests.get(f"{base_url}/cameras")
            # May fail due to no actual cameras, but should not be 404
            assert camera_response.status_code in [200, 500, 503]
        
        if "screenshots" in endpoints:
            # Should be OrangePi
            screenshot_response = requests.get(f"{base_url}/screenshots/history")
            # May fail due to no display, but should not be 404  
            assert screenshot_response.status_code in [200, 500, 503]
    
    def test_error_handling_workflow(self, api_server):
        """Test error handling in real deployment."""
        base_url = "http://localhost:9090"
        
        # Test 404 handling
        response = requests.get(f"{base_url}/nonexistent")
        assert response.status_code == 404
        
        # Test method not allowed
        response = requests.post(f"{base_url}/platform")
        assert response.status_code == 405
        
        # Test invalid endpoints
        response = requests.get(f"{base_url}/invalid/path")
        assert response.status_code == 404


@pytest.mark.integration
class TestConfigurationScenarios:
    """Test different configuration scenarios."""
    
    def test_environment_variable_override(self, monkeypatch):
        """Test configuration via environment variables."""
        # Override platform detection
        monkeypatch.setenv("PLATFORM_OVERRIDE", "orangepi")
        monkeypatch.setenv("OAAPI_PORT", "9091")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        # Import after setting env vars
        from src.oaDeviceAPI.core.config import settings, detect_platform
        
        assert detect_platform() == "orangepi"
        assert settings.port == 9091
        assert settings.log_level == "DEBUG"
    
    def test_platform_detection_scenarios(self):
        """Test platform detection under different scenarios."""
        test_cases = [
            ("Darwin", "macos"),
            ("Linux", "orangepi"),  # Default for Linux
        ]
        
        for system_name, expected_platform in test_cases:
            with patch("platform.system", return_value=system_name):
                from src.oaDeviceAPI.core.config import detect_platform
                detected = detect_platform()
                assert detected == expected_platform
    
    def test_feature_availability_matrix(self):
        """Test feature availability across platforms."""
        from src.oaDeviceAPI.core.config import PLATFORM_CONFIG
        
        # Validate configuration matrix
        for platform, config in PLATFORM_CONFIG.items():
            assert "service_manager" in config
            assert "bin_paths" in config
            assert isinstance(config["bin_paths"], list)
            
            # Validate feature flags
            feature_flags = [
                "screenshot_supported",
                "camera_supported", 
                "tracker_supported",
                "camguard_supported"
            ]
            for flag in feature_flags:
                assert flag in config
                assert isinstance(config[flag], bool)


class TestPerformanceScenarios:
    """Test performance under various scenarios."""
    
    @pytest.mark.slow
    def test_concurrent_health_requests(self, api_server):
        """Test handling concurrent health requests."""
        import concurrent.futures
        import threading
        
        def make_request():
            response = requests.get("http://localhost:9090/health", timeout=10)
            return response.status_code
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    def test_memory_usage_stability(self, api_server):
        """Test memory usage remains stable.""" 
        import psutil
        import time
        
        # Get initial memory usage
        process = psutil.Process(api_server.pid)
        initial_memory = process.memory_info().rss
        
        # Make multiple requests
        for _ in range(50):
            requests.get("http://localhost:9090/health")
            time.sleep(0.1)
        
        # Check memory usage hasn't grown significantly
        final_memory = process.memory_info().rss
        memory_growth = (final_memory - initial_memory) / initial_memory
        
        # Allow up to 20% memory growth
        assert memory_growth < 0.20
    
    def test_response_time_consistency(self, api_server):
        """Test response time consistency."""
        import time
        
        response_times = []
        
        for _ in range(20):
            start_time = time.time()
            response = requests.get("http://localhost:9090/health")
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        # Calculate statistics
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        
        # Response times should be reasonable
        assert avg_time < 1.0  # Average under 1 second
        assert max_time < 2.0  # Max under 2 seconds