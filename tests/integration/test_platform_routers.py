"""Integration tests for platform-specific router loading."""

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


class TestPlatformRouterLoading:
    """Test dynamic platform router loading."""

    def test_macos_routers_loaded(self, mock_macos_platform, mock_psutil):
        """Test that macOS routers are loaded correctly."""
        with patch("src.oaDeviceAPI.platforms.macos.routers.health") as mock_health, \
             patch("src.oaDeviceAPI.platforms.macos.routers.camera") as mock_camera, \
             patch("src.oaDeviceAPI.platforms.macos.routers.tracker") as mock_tracker:

            # Mock router objects
            mock_health.router = Mock()
            mock_camera.router = Mock()
            mock_tracker.router = Mock()

            # Import after mocking platform detection
            from main import app
            client = TestClient(app)

            response = client.get("/")
            assert response.status_code == 200

            data = response.json()
            assert data["platform"]["platform"] == "macos"
            assert "cameras" in data["endpoints"]
            assert "tracker" in data["endpoints"]

    def test_orangepi_routers_loaded(self, mock_orangepi_platform, mock_psutil):
        """Test that OrangePi routers are loaded correctly."""
        with patch("src.oaDeviceAPI.platforms.orangepi.routers.health") as mock_health, \
             patch("src.oaDeviceAPI.platforms.orangepi.routers.screenshots") as mock_screenshots:

            # Mock router objects
            mock_health.router = Mock()
            mock_screenshots.router = Mock()

            from main import app
            client = TestClient(app)

            response = client.get("/")
            assert response.status_code == 200

            data = response.json()
            assert data["platform"]["platform"] == "orangepi"
            assert "screenshots" in data["endpoints"]
            assert "cameras" not in data["endpoints"]

    def test_router_import_failure_handled(self, mock_macos_platform, mock_psutil):
        """Test graceful handling of router import failures."""
        with patch("src.oaDeviceAPI.platforms.macos.routers.camera", side_effect=ImportError("Camera module not found")):

            # Should not crash, just log the error
            from main import app
            client = TestClient(app)

            response = client.get("/")
            assert response.status_code == 200

            # App should still start but without camera functionality
            data = response.json()
            assert data["status"] == "running"


class TestPlatformSpecificEndpoints:
    """Test platform-specific endpoint availability."""

    def test_macos_specific_endpoints(self, test_client_macos):
        """Test macOS-specific endpoints are available."""
        response = test_client_macos.get("/")
        data = response.json()

        # Check for macOS-specific endpoints
        expected_endpoints = ["cameras", "tracker", "camguard"]
        for endpoint in expected_endpoints:
            assert endpoint in data["endpoints"], f"Missing {endpoint} endpoint for macOS"

        # Check for macOS-specific actions
        assert "restart_tracker" in data["endpoints"]["actions"]

        # Should NOT have OrangePi endpoints
        assert "screenshots" not in data["endpoints"]
        assert "restart_player" not in data["endpoints"]["actions"]

    def test_orangepi_specific_endpoints(self, test_client_orangepi):
        """Test OrangePi-specific endpoints are available."""
        response = test_client_orangepi.get("/")
        data = response.json()

        # Check for OrangePi-specific endpoints
        expected_endpoints = ["screenshots"]
        for endpoint in expected_endpoints:
            assert endpoint in data["endpoints"], f"Missing {endpoint} endpoint for OrangePi"

        # Check for OrangePi-specific actions
        assert "restart_player" in data["endpoints"]["actions"]

        # Should NOT have macOS endpoints
        assert "cameras" not in data["endpoints"]
        assert "tracker" not in data["endpoints"]
        assert "restart_tracker" not in data["endpoints"]["actions"]


class TestFeatureDetection:
    """Test feature detection and conditional endpoint exposure."""

    def test_feature_based_endpoint_exposure(self, mock_macos_platform):
        """Test that endpoints are exposed based on feature support."""
        with patch("src.oaDeviceAPI.core.platform.platform_manager") as mock_pm:
            mock_pm.supports_feature.side_effect = lambda f: {
                "camera": True,
                "tracker": False,  # Tracker disabled
                "camguard": True,
                "screenshot": False
            }.get(f, False)

            mock_pm.get_platform_info.return_value = {
                "platform": "macos",
                "features": {"camera": True, "tracker": False, "camguard": True, "screenshot": False}
            }

            from main import app
            client = TestClient(app)

            response = client.get("/")
            data = response.json()

            # Should have camera and camguard, but not tracker
            assert "cameras" in data["endpoints"]
            assert "camguard" in data["endpoints"]
            assert "tracker" not in data["endpoints"]

    def test_no_features_fallback(self, mock_generic_platform):
        """Test fallback when no platform features are available."""
        with patch("src.oaDeviceAPI.core.platform.platform_manager") as mock_pm:
            mock_pm.supports_feature.return_value = False
            mock_pm.get_platform_info.return_value = {
                "platform": "linux",
                "features": {"camera": False, "tracker": False, "screenshot": False}
            }

            from main import app
            client = TestClient(app)

            response = client.get("/")
            data = response.json()

            # Should only have basic endpoints
            basic_endpoints = ["platform", "health", "health_summary"]
            for endpoint in basic_endpoints:
                assert endpoint in data["endpoints"]

            # Should not have any platform-specific endpoints
            assert "cameras" not in data["endpoints"]
            assert "screenshots" not in data["endpoints"]
            assert "tracker" not in data["endpoints"]


class TestCrossCompatibility:
    """Test API compatibility across different platform configurations."""

    def test_health_endpoint_cross_platform(self, mock_psutil):
        """Test health endpoint works consistently across platforms."""
        platforms = ["macos", "orangepi"]

        for platform in platforms:
            with patch("src.oaDeviceAPI.core.config.detect_platform", return_value=platform):
                from main import app
                client = TestClient(app)

                response = client.get("/health")
                assert response.status_code == 200

                data = response.json()
                required_keys = ["status", "hostname", "timestamp", "metrics"]
                for key in required_keys:
                    assert key in data, f"Missing {key} in {platform} health response"

    def test_platform_info_consistency(self):
        """Test platform info endpoint consistency."""
        platforms = ["macos", "orangepi", "linux"]

        for platform in platforms:
            with patch("src.oaDeviceAPI.core.config.detect_platform", return_value=platform):
                from main import app
                client = TestClient(app)

                response = client.get("/platform")
                assert response.status_code == 200

                data = response.json()
                assert data["platform"] == platform
                assert "features" in data
                assert "service_manager" in data

    def test_error_handling_consistency(self):
        """Test that error responses are consistent across platforms."""
        platforms = ["macos", "orangepi"]

        for platform in platforms:
            with patch("src.oaDeviceAPI.core.config.detect_platform", return_value=platform):
                from main import app
                client = TestClient(app)

                # Test non-existent endpoint
                response = client.get("/nonexistent")
                assert response.status_code == 404

                # Test method not allowed
                response = client.post("/platform")
                assert response.status_code == 405
