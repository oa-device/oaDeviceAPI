#!/usr/bin/env python3
"""
Comprehensive test suite for the unified oaDeviceAPI

This test suite validates all major endpoints and functionality
of the unified Device API that works across macOS and OrangePi platforms.
"""

import pytest
import requests
import json
import time
from typing import Dict, Any

# Test configuration
API_BASE_URL = "http://localhost:9090"
TIMEOUT = 10


class TestUnifiedAPI:
    """Test suite for the unified Device API"""

    @pytest.fixture(scope="session", autouse=True)
    def ensure_api_running(self):
        """Ensure the API is running before tests start"""
        try:
            response = requests.get(f"{API_BASE_URL}/", timeout=TIMEOUT)
            if response.status_code != 200:
                pytest.skip("API not running - start with: python main.py")
        except requests.exceptions.ConnectionError:
            pytest.skip("API not running - start with: python main.py")

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        response = requests.get(f"{API_BASE_URL}/", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "OrangeAd Unified Device API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "platform" in data
        assert "endpoints" in data

    def test_platform_detection(self):
        """Test platform detection endpoint"""
        response = requests.get(f"{API_BASE_URL}/platform", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        # Platform should be detected as either 'macos' or 'orangepi'
        assert data["platform"] in ["macos", "orangepi"]
        assert "service_manager" in data
        assert "features" in data

    def test_health_endpoint(self):
        """Test the main health endpoint"""
        response = requests.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "hostname" in data
        assert "timestamp" in data
        assert "metrics" in data
        assert "device_info" in data
        assert "capabilities" in data

    def test_health_summary(self):
        """Test the health summary endpoint"""
        response = requests.get(f"{API_BASE_URL}/health/summary", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "scores" in data
        # Should have some form of health status
        assert "warnings" in data or "recommendations" in data

    def test_camera_endpoints(self):
        """Test camera-related endpoints"""
        # Test camera list
        response = requests.get(f"{API_BASE_URL}/cameras", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "cameras" in data
        assert "count" in data
        assert "device_has_camera_support" in data

        # Test camera status
        response = requests.get(f"{API_BASE_URL}/cameras/status", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "camera_count" in data
        assert "cameras" in data

    def test_tracker_endpoints(self):
        """Test tracker-related endpoints"""
        # Test tracker status
        response = requests.get(f"{API_BASE_URL}/tracker/status", timeout=TIMEOUT)
        assert response.status_code == 200
        
        data = response.json()
        assert "service" in data
        assert "api" in data
        assert "healthy" in data

        # Test tracker stats (may fail if tracker not running - that's OK)
        response = requests.get(f"{API_BASE_URL}/tracker/stats", timeout=TIMEOUT)
        # Don't assert on status code since tracker might not be running
        # Just ensure it returns JSON
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_action_endpoints(self):
        """Test action endpoints (non-destructive tests only)"""
        # Test restart tracker action (POST request)
        response = requests.post(f"{API_BASE_URL}/actions/restart-tracker", timeout=TIMEOUT)
        # Should return a response (might fail if no tracker, that's OK)
        assert response.status_code in [200, 404, 500]  # Various valid responses
        
        data = response.json()
        assert isinstance(data, dict)

        # Note: We don't test reboot action as it would actually reboot the system

    def test_error_handling(self):
        """Test API error handling"""
        # Test non-existent endpoint
        response = requests.get(f"{API_BASE_URL}/nonexistent", timeout=TIMEOUT)
        assert response.status_code == 404

        # Test invalid camera ID
        response = requests.get(f"{API_BASE_URL}/cameras/invalid-id", timeout=TIMEOUT)
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data or "message" in data

    def test_api_consistency(self):
        """Test API response consistency and structure"""
        # All endpoints should return JSON
        endpoints_to_test = [
            "/",
            "/platform", 
            "/health",
            "/health/summary",
            "/cameras",
            "/cameras/status",
            "/tracker/status"
        ]
        
        for endpoint in endpoints_to_test:
            response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=TIMEOUT)
            assert response.status_code == 200
            
            # Should be valid JSON
            data = response.json()
            assert isinstance(data, dict)
            
            # Should have timestamp if it's a data endpoint
            if endpoint not in ["/", "/platform"]:
                # Either has timestamp directly or in nested structure
                json_str = json.dumps(data)
                assert "timestamp" in json_str

    def test_platform_specific_features(self):
        """Test that platform-specific features are properly detected"""
        platform_response = requests.get(f"{API_BASE_URL}/platform", timeout=TIMEOUT)
        platform_data = platform_response.json()
        platform_type = platform_data["platform"]
        
        root_response = requests.get(f"{API_BASE_URL}/", timeout=TIMEOUT)
        root_data = root_response.json()
        features = root_data["platform"]["features"]
        
        if platform_type == "macos":
            # macOS should have camera and tracker support
            assert features.get("camera", False) == True
            assert features.get("tracker", False) == True
            # macOS typically doesn't have screenshot support
            assert features.get("screenshot", True) == False
            
        elif platform_type == "orangepi":
            # OrangePi should have screenshot support
            assert features.get("screenshot", False) == True


class TestAPIPerformance:
    """Performance tests for the API"""

    def test_response_times(self):
        """Test that API responses are reasonably fast"""
        start_time = time.time()
        response = requests.get(f"{API_BASE_URL}/", timeout=TIMEOUT)
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 2.0  # Should respond within 2 seconds

    def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request():
            try:
                response = requests.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
                results.put(response.status_code)
            except Exception as e:
                results.put(f"Error: {e}")
        
        # Create 5 concurrent threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check all requests succeeded
        while not results.empty():
            result = results.get()
            assert result == 200, f"Expected 200, got {result}"


if __name__ == "__main__":
    print("Running unified API tests...")
    print(f"Testing API at: {API_BASE_URL}")
    print()
    print("Make sure the API is running with: python main.py")
    print()
    
    # Run pytest
    pytest.main([__file__, "-v", "--tb=short"])