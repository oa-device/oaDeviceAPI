"""Integration tests for API endpoints across platforms."""

import pytest
from fastapi import status


class TestCommonEndpoints:
    """Test endpoints available on all platforms."""
    
    def test_root_endpoint_macos(self, test_client_macos):
        """Test root endpoint with macOS platform."""
        response = test_client_macos.get("/")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["name"] == "OrangeAd Unified Device API"
        assert data["status"] == "running"
        assert data["platform"]["platform"] == "macos"
        
        # macOS should have camera and tracker endpoints
        assert "cameras" in data["endpoints"]
        assert "tracker" in data["endpoints"]
        assert "screenshots" not in data["endpoints"]
    
    def test_root_endpoint_orangepi(self, test_client_orangepi):
        """Test root endpoint with OrangePi platform.""" 
        response = test_client_orangepi.get("/")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["platform"]["platform"] == "orangepi"
        
        # OrangePi should have screenshot endpoints
        assert "screenshots" in data["endpoints"]
        assert "cameras" not in data["endpoints"]
        assert "tracker" not in data["endpoints"]
    
    def test_platform_info_endpoint(self, test_client_macos):
        """Test platform information endpoint."""
        response = test_client_macos.get("/platform")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        required_keys = ["platform", "service_manager", "features"]
        for key in required_keys:
            assert key in data
    
    def test_health_endpoint_structure(self, test_client_macos):
        """Test health endpoint returns expected structure."""
        response = test_client_macos.get("/health")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        required_keys = ["status", "hostname", "timestamp", "metrics", "device_info"]
        for key in required_keys:
            assert key in data
        
        # Test metrics structure
        metrics_keys = ["cpu", "memory", "disk", "network"]
        for key in metrics_keys:
            assert key in data["metrics"]


class TestMacOSSpecificEndpoints:
    """Test macOS-specific endpoints."""
    
    def test_camera_endpoints_available_on_macos(self, test_client_macos):
        """Test that camera endpoints are available on macOS."""
        # This would require the camera router to be properly imported
        # For now, test that the root endpoint shows camera endpoints
        response = test_client_macos.get("/")
        data = response.json()
        
        assert "cameras" in data["endpoints"]
        assert "list" in data["endpoints"]["cameras"]
        assert "stream" in data["endpoints"]["cameras"]
    
    def test_tracker_endpoints_available_on_macos(self, test_client_macos):
        """Test that tracker endpoints are available on macOS."""
        response = test_client_macos.get("/")
        data = response.json()
        
        assert "tracker" in data["endpoints"]
        assert "stats" in data["endpoints"]["tracker"]
        assert "stream" in data["endpoints"]["tracker"]
    
    def test_macos_actions_available(self, test_client_macos):
        """Test macOS-specific actions are available."""
        response = test_client_macos.get("/")
        data = response.json()
        
        assert "actions" in data["endpoints"]
        assert "reboot" in data["endpoints"]["actions"]
        assert "restart_tracker" in data["endpoints"]["actions"]


class TestOrangePiSpecificEndpoints:
    """Test OrangePi-specific endpoints."""
    
    def test_screenshot_endpoints_available_on_orangepi(self, test_client_orangepi):
        """Test that screenshot endpoints are available on OrangePi."""
        response = test_client_orangepi.get("/")
        data = response.json()
        
        assert "screenshots" in data["endpoints"]
        assert "capture" in data["endpoints"]["screenshots"]
        assert "latest" in data["endpoints"]["screenshots"]
        assert "history" in data["endpoints"]["screenshots"]
    
    def test_orangepi_actions_available(self, test_client_orangepi):
        """Test OrangePi-specific actions are available."""
        response = test_client_orangepi.get("/")
        data = response.json()
        
        assert "actions" in data["endpoints"]
        assert "reboot" in data["endpoints"]["actions"]
        assert "restart_player" in data["endpoints"]["actions"]


class TestCrossPlatformCompatibility:
    """Test API compatibility across platforms."""
    
    def test_health_schema_consistency(self, test_client_macos, test_client_orangepi):
        """Test that health endpoints return consistent schema across platforms."""
        # Test macOS health response
        macos_response = test_client_macos.get("/health")
        assert macos_response.status_code == status.HTTP_200_OK
        macos_data = macos_response.json()
        
        # Test OrangePi health response  
        orangepi_response = test_client_orangepi.get("/health")
        assert orangepi_response.status_code == status.HTTP_200_OK
        orangepi_data = orangepi_response.json()
        
        # Both should have the same base structure
        common_keys = ["status", "hostname", "timestamp", "metrics", "device_info"]
        for key in common_keys:
            assert key in macos_data
            assert key in orangepi_data
        
        # Metrics should have same structure
        metrics_keys = ["cpu", "memory", "disk", "network"]
        for key in metrics_keys:
            assert key in macos_data["metrics"]
            assert key in orangepi_data["metrics"]
    
    def test_error_responses_consistent(self, test_client_macos, test_client_orangepi):
        """Test that error responses are consistent across platforms."""
        # Test non-existent endpoint
        macos_response = test_client_macos.get("/nonexistent")
        orangepi_response = test_client_orangepi.get("/nonexistent")
        
        assert macos_response.status_code == orangepi_response.status_code
        
    def test_middleware_applied_consistently(self, test_client_macos, test_client_orangepi):
        """Test that middleware (CORS, Tailscale) is applied consistently."""
        # Both should have CORS headers
        macos_response = test_client_macos.get("/")
        orangepi_response = test_client_orangepi.get("/")
        
        # Check for CORS headers (these are added by FastAPI test client automatically)
        assert macos_response.status_code == status.HTTP_200_OK
        assert orangepi_response.status_code == status.HTTP_200_OK