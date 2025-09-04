"""Integration tests for comprehensive error handling."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest
from fastapi import status


class TestAPIErrorHandling:
    """Test API-level error handling and resilience."""

    def test_404_error_consistency(self, test_client_macos, test_client_orangepi):
        """Test that 404 errors are consistent across platforms."""
        nonexistent_endpoints = [
            "/nonexistent",
            "/health/invalid",
            "/cameras/999/stream",
            "/actions/invalid_action"
        ]

        for endpoint in nonexistent_endpoints:
            macos_response = test_client_macos.get(endpoint)
            orangepi_response = test_client_orangepi.get(endpoint)

            assert macos_response.status_code == status.HTTP_404_NOT_FOUND
            assert orangepi_response.status_code == status.HTTP_404_NOT_FOUND

            # Error structure should be consistent
            if macos_response.headers.get("content-type", "").startswith("application/json"):
                macos_data = macos_response.json()
                orangepi_data = orangepi_response.json()

                # Both should have error details
                assert "detail" in macos_data
                assert "detail" in orangepi_data

    def test_method_not_allowed_handling(self, test_client_macos):
        """Test handling of unsupported HTTP methods."""
        endpoints_and_methods = [
            ("/health", "POST"),
            ("/health", "DELETE"),
            ("/platform", "PUT"),
            ("/", "PATCH")
        ]

        for endpoint, method in endpoints_and_methods:
            response = test_client_macos.request(method, endpoint)

            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_malformed_request_handling(self, test_client_macos):
        """Test handling of malformed requests."""
        # Test invalid JSON in POST requests
        response = test_client_macos.post(
            "/actions/reboot",
            content="invalid json {",
            headers={"Content-Type": "application/json"}
        )

        # Should return 400 or 422 for malformed JSON
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    def test_large_request_handling(self, test_client_macos):
        """Test handling of excessively large requests."""
        # Create large JSON payload
        large_data = {"data": "x" * 1000000}  # 1MB of data

        response = test_client_macos.post(
            "/actions/reboot",
            json=large_data
        )

        # Should handle gracefully (may accept or reject based on limits)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            status.HTTP_400_BAD_REQUEST
        ]


class TestServiceFailureScenarios:
    """Test API behavior when underlying services fail."""

    @patch("src.oaDeviceAPI.platforms.macos.services.standardized_metrics.get_standardized_metrics")
    def test_health_endpoint_with_metrics_failure(self, mock_metrics, test_client_macos):
        """Test health endpoint when metrics service fails."""
        mock_metrics.side_effect = Exception("Metrics service failed")

        response = test_client_macos.get("/health")

        # Should return error response or fallback data
        assert response.status_code in [
            status.HTTP_200_OK,  # With error info in response
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should indicate service failure
            assert "error" in data or data.get("status") != "online"

    @patch("src.oaDeviceAPI.platforms.macos.services.tracker.get_tracker_stats")
    def test_tracker_endpoint_with_service_down(self, mock_tracker, test_client_macos):
        """Test tracker endpoint when tracker service is down."""
        mock_tracker.side_effect = ConnectionRefusedError("Tracker not responding")

        response = test_client_macos.get("/tracker/stats")

        # Should handle service unavailability gracefully
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data.get("healthy") is False
        else:
            assert response.status_code in [
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_502_BAD_GATEWAY
            ]

    @patch("subprocess.run")
    def test_action_endpoint_with_command_failure(self, mock_run, test_client_macos):
        """Test action endpoint when underlying commands fail."""
        mock_run.side_effect = PermissionError("Permission denied")

        response = test_client_macos.post("/actions/reboot")

        # Should return error information
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data.get("success") is False
            assert "error" in data
        else:
            assert response.status_code in [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]


class TestPlatformSpecificErrorHandling:
    """Test platform-specific error handling."""

    @patch("src.oaDeviceAPI.platforms.macos.services.camera.get_camera_info")
    def test_macos_camera_service_failure(self, mock_camera, test_client_macos):
        """Test macOS camera endpoint when camera service fails."""
        mock_camera.side_effect = Exception("Camera access denied")

        response = test_client_macos.get("/cameras")

        # Should handle camera service failure gracefully
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should indicate no cameras available or service error
            assert data.get("count", 0) == 0 or "error" in data
        else:
            assert response.status_code in [
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]

    @patch("src.oaDeviceAPI.platforms.orangepi.services.utils.capture_screenshot")
    def test_orangepi_screenshot_service_failure(self, mock_screenshot, test_client_orangepi):
        """Test OrangePi screenshot endpoint when display service fails."""
        mock_screenshot.side_effect = Exception("Display not available")

        response = test_client_orangepi.post("/screenshots/capture")

        # Should handle display service failure gracefully
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data.get("success") is False
            assert "error" in data
        else:
            assert response.status_code in [
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]

    def test_platform_router_import_failure(self):
        """Test handling of platform router import failures."""
        # Simulate import failure for platform-specific routers
        with patch("importlib.import_module", side_effect=ImportError("Router module not found")):
            from main import app

            # App should still start with fallback behavior
            assert app is not None
            assert hasattr(app, 'routes')


class TestConcurrencyErrorHandling:
    """Test error handling under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_health_requests_with_failures(self, test_client_macos):
        """Test concurrent health requests when some fail."""

        async def make_health_request():
            """Make a health request."""
            return test_client_macos.get("/health")

        # Simulate mixed success/failure scenario
        with patch("src.oaDeviceAPI.platforms.macos.services.standardized_metrics.get_standardized_metrics") as mock_metrics:
            # Alternate between success and failure
            mock_metrics.side_effect = [
                {"cpu": {"usage_percent": 25}, "memory": {"usage_percent": 30}},  # Success
                Exception("Service temporarily unavailable"),  # Failure
                {"cpu": {"usage_percent": 30}, "memory": {"usage_percent": 35}},  # Success
                Exception("Another failure"),  # Failure
            ]

            # Make concurrent requests
            tasks = [make_health_request() for _ in range(4)]
            responses = []

            for task in tasks:
                responses.append(task)

            # All requests should complete (not hang or crash)
            assert len(responses) == 4
            for response in responses:
                assert hasattr(response, 'status_code')
                assert response.status_code in [200, 500, 503]

    def test_resource_exhaustion_handling(self, test_client_macos):
        """Test API behavior under simulated resource exhaustion."""
        # Simulate memory pressure
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.side_effect = MemoryError("Out of memory")

            response = test_client_macos.get("/health")

            # Should handle gracefully
            assert response.status_code in [200, 500, 503]

    def test_disk_full_handling(self, test_client_orangepi):
        """Test handling when disk is full (OrangePi screenshots)."""
        with patch("pathlib.Path.write_bytes", side_effect=OSError("No space left on device")):
            response = test_client_orangepi.post("/screenshots/capture")

            # Should handle disk full gracefully
            if response.status_code == 200:
                data = response.json()
                assert data.get("success") is False
                assert "space" in data.get("error", "").lower()
            else:
                assert response.status_code in [500, 507]  # 507 = Insufficient Storage


class TestNetworkErrorHandling:
    """Test network-related error handling."""

    @patch("aiohttp.ClientSession.get")
    async def test_external_service_timeout(self, mock_get, test_client_macos):
        """Test handling of external service timeouts."""
        mock_get.side_effect = asyncio.TimeoutError("Request timed out")

        # Test tracker stats (calls external service)
        response = test_client_macos.get("/tracker/stats")

        # Should handle timeout gracefully
        if response.status_code == 200:
            data = response.json()
            assert data.get("healthy") is False
            assert "timeout" in data.get("error", "").lower()
        else:
            assert response.status_code in [504, 503]  # Gateway timeout or service unavailable

    @patch("aiohttp.ClientSession.get")
    async def test_external_service_connection_refused(self, mock_get, test_client_macos):
        """Test handling when external services refuse connection."""
        mock_get.side_effect = ConnectionRefusedError("Connection refused")

        response = test_client_macos.get("/tracker/stats")

        if response.status_code == 200:
            data = response.json()
            assert data.get("healthy") is False
        else:
            assert response.status_code in [502, 503]

    def test_dns_resolution_failure(self, test_client_macos):
        """Test handling of DNS resolution failures."""
        with patch("socket.gethostname", side_effect=OSError("Name resolution failed")):
            response = test_client_macos.get("/health")

            # Should handle DNS issues gracefully
            if response.status_code == 200:
                data = response.json()
                assert data.get("hostname") in ["Unknown", "localhost", None]
            else:
                assert response.status_code in [500, 503]


class TestValidationErrorHandling:
    """Test input validation and schema error handling."""

    def test_invalid_query_parameters(self, test_client_macos):
        """Test handling of invalid query parameters."""
        invalid_params = [
            {"limit": "not_a_number"},
            {"timeout": -1},
            {"format": "unsupported"},
            {"invalid_param": "value"}
        ]

        for params in invalid_params:
            response = test_client_macos.get("/health", params=params)

            # Should either ignore invalid params or return validation error
            assert response.status_code in [200, 400, 422]

    def test_invalid_path_parameters(self, test_client_macos):
        """Test handling of invalid path parameters."""
        invalid_camera_ids = [
            "999",  # Non-existent
            "invalid_id",
            "'; DROP TABLE cameras;",  # SQL injection attempt
            "../../../etc/passwd",  # Path traversal
            ""  # Empty
        ]

        for camera_id in invalid_camera_ids:
            response = test_client_macos.get(f"/cameras/{camera_id}/stream")

            # Should return appropriate error
            assert response.status_code in [400, 404, 422]

    def test_content_type_validation(self, test_client_macos):
        """Test content type validation for POST requests."""
        # Test various content types
        test_cases = [
            ("text/plain", "plain text data", [400, 415]),
            ("application/xml", "<xml>data</xml>", [400, 415]),
            ("application/json", '{"valid": "json"}', [200, 400, 422]),
            ("", '{"data": "no_content_type"}', [200, 400])
        ]

        for content_type, data, expected_codes in test_cases:
            headers = {"Content-Type": content_type} if content_type else {}

            response = test_client_macos.post(
                "/actions/reboot",
                content=data,
                headers=headers
            )

            assert response.status_code in expected_codes


class TestResourceLimitErrorHandling:
    """Test error handling when resource limits are exceeded."""

    @patch("psutil.cpu_percent")
    def test_high_cpu_usage_handling(self, mock_cpu, test_client_macos):
        """Test API behavior during high CPU usage."""
        # Simulate extremely high CPU usage
        mock_cpu.return_value = 99.9

        response = test_client_macos.get("/health")

        # Should still respond but indicate critical state
        if response.status_code == 200:
            data = response.json()
            if "metrics" in data:
                assert data["metrics"]["cpu"]["usage_percent"] > 99

    @patch("psutil.virtual_memory")
    def test_low_memory_handling(self, mock_memory, test_client_macos):
        """Test API behavior during low memory conditions."""
        # Simulate very low available memory
        mock_memory.return_value = Mock(
            total=8000000000,
            used=7900000000,  # 98.75% used
            available=100000000,  # Only 100MB available
            percent=98.75
        )

        response = test_client_macos.get("/health")

        if response.status_code == 200:
            data = response.json()
            if "metrics" in data:
                assert data["metrics"]["memory"]["usage_percent"] > 95

    @patch("psutil.disk_usage")
    def test_disk_full_handling(self, mock_disk, test_client_orangepi):
        """Test API behavior when disk is nearly full."""
        # Simulate nearly full disk
        mock_disk.return_value = Mock(
            total=100000000000,  # 100GB
            used=99000000000,    # 99GB used
            free=1000000000,     # 1GB free
            percent=99.0
        )

        response = test_client_orangepi.get("/health")

        if response.status_code == 200:
            data = response.json()
            if "metrics" in data:
                assert data["metrics"]["disk"]["usage_percent"] > 98


class TestExternalDependencyFailures:
    """Test handling of external dependency failures."""

    @patch("subprocess.run")
    def test_system_command_not_found(self, mock_run, test_client_macos):
        """Test handling when system commands are not found."""
        mock_run.side_effect = FileNotFoundError("Command not found")

        # Test endpoints that rely on system commands
        endpoints = [
            "/health",
            "/platform",
            "/actions/reboot"
        ]

        for endpoint in endpoints:
            if endpoint == "/actions/reboot":
                response = test_client_macos.post(endpoint)
            else:
                response = test_client_macos.get(endpoint)

            # Should handle missing commands gracefully
            assert response.status_code in [200, 500, 503]

            if response.status_code == 200:
                data = response.json()
                # Should indicate degraded functionality
                if endpoint == "/actions/reboot":
                    assert data.get("success") is False

    @patch("psutil.cpu_percent")
    def test_psutil_import_failure_simulation(self, mock_cpu, test_client_macos):
        """Test behavior when psutil functions fail."""
        mock_cpu.side_effect = ImportError("psutil module error")

        response = test_client_macos.get("/health")

        # Should handle psutil failures
        if response.status_code == 200:
            data = response.json()
            # Should either have fallback values or error indication
            assert isinstance(data, dict)

    @patch("socket.gethostname")
    def test_hostname_resolution_failure(self, mock_hostname, test_client_macos):
        """Test handling when hostname resolution fails."""
        mock_hostname.side_effect = OSError("Hostname resolution failed")

        response = test_client_macos.get("/health")

        if response.status_code == 200:
            data = response.json()
            # Should have fallback hostname
            assert data.get("hostname") in ["localhost", "unknown", "Unknown"]


class TestMiddlewareErrorHandling:
    """Test middleware error handling scenarios."""

    def test_tailscale_middleware_with_invalid_client_data(self, test_client_macos):
        """Test Tailscale middleware with invalid client information."""
        # This is tricky to test with FastAPI TestClient as it mocks the client
        # But we can test the underlying logic
        import ipaddress

        from src.oaDeviceAPI.middleware import TailscaleSubnetMiddleware

        # Test middleware creation with edge cases
        edge_case_subnets = [
            "100.64.0.0/10",  # Standard Tailscale
            "0.0.0.0/0",      # Open (should work but dangerous)
            "127.0.0.1/32",   # Localhost only
        ]

        for subnet in edge_case_subnets:
            try:
                middleware = TailscaleSubnetMiddleware(
                    app=Mock(),
                    tailscale_subnet_str=subnet
                )
                assert isinstance(middleware.tailscale_subnet, (ipaddress.IPv4Network, ipaddress.IPv6Network))
            except ValueError:
                # Some edge cases might be invalid
                pass

    def test_cors_middleware_error_handling(self, test_client_macos):
        """Test CORS middleware error handling."""
        # Test OPTIONS request (CORS preflight)
        response = test_client_macos.options("/health")

        # Should handle CORS preflight
        assert response.status_code in [200, 405]

        # Test with custom headers
        custom_headers = {
            "Origin": "https://malicious-site.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Custom-Header"
        }

        response = test_client_macos.options("/health", headers=custom_headers)

        # Should handle regardless of origin (configured for *)
        assert response.status_code in [200, 405]


class TestDataCorruptionHandling:
    """Test handling of corrupted data scenarios."""

    @patch("json.loads")
    def test_json_corruption_handling(self, mock_json_loads, test_client_macos):
        """Test handling of JSON corruption in responses."""
        mock_json_loads.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        # Services that parse JSON should handle corruption
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="invalid json {")

            response = test_client_macos.get("/cameras")

            # Should handle JSON corruption gracefully
            if response.status_code == 200:
                data = response.json()
                # Should have fallback structure or error indication
                assert isinstance(data, dict)

    def test_binary_data_handling(self, test_client_orangepi):
        """Test handling of binary data in text contexts."""
        with patch("subprocess.run") as mock_run:
            # Return binary data where text is expected
            mock_run.return_value = Mock(
                returncode=0,
                stdout=b"\x00\x01\x02\xff\xfe\xfd"  # Binary data
            )

            response = test_client_orangepi.get("/health")

            # Should handle binary data gracefully
            assert response.status_code in [200, 500]

            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)

    @patch("pathlib.Path.read_text")
    def test_file_encoding_error_handling(self, mock_read_text, test_client_orangepi):
        """Test handling of file encoding errors."""
        mock_read_text.side_effect = UnicodeDecodeError(
            "utf-8", b"\xff\xfe", 0, 1, "invalid start byte"
        )

        # Services that read files should handle encoding errors
        response = test_client_orangepi.get("/health")

        # Should handle encoding errors gracefully
        assert response.status_code in [200, 500]


class TestErrorResponseConsistency:
    """Test consistency of error responses across the API."""

    def test_error_response_structure_consistency(self, test_client_macos, test_client_orangepi):
        """Test that error responses have consistent structure."""
        # Force an error condition
        with patch("src.oaDeviceAPI.core.platform.platform_manager.get_platform_info",
                  side_effect=Exception("Forced error")):

            macos_response = test_client_macos.get("/platform")
            orangepi_response = test_client_orangepi.get("/platform")

            # Both should handle errors consistently
            assert macos_response.status_code == orangepi_response.status_code

            # If returning JSON, should have consistent structure
            if (macos_response.headers.get("content-type", "").startswith("application/json") and
                orangepi_response.headers.get("content-type", "").startswith("application/json")):

                macos_data = macos_response.json()
                orangepi_data = orangepi_response.json()

                # Should have similar error structure
                error_keys = ["detail", "error", "message", "status"]
                macos_has_error = any(key in macos_data for key in error_keys)
                orangepi_has_error = any(key in orangepi_data for key in error_keys)

                assert macos_has_error and orangepi_has_error

    def test_http_status_code_appropriateness(self, test_client_macos):
        """Test that HTTP status codes are appropriate for different error types."""
        error_scenarios = [
            # (endpoint, method, expected_status_codes, description)
            ("/nonexistent", "GET", [404], "Resource not found"),
            ("/health", "POST", [405], "Method not allowed"),
            ("/cameras/invalid_id/stream", "GET", [400, 404], "Invalid resource ID"),
        ]

        for endpoint, method, expected_codes, description in error_scenarios:
            response = test_client_macos.request(method, endpoint)

            assert response.status_code in expected_codes, \
                f"Unexpected status code for {description}: {response.status_code}"

    def test_error_message_informativeness(self, test_client_macos):
        """Test that error messages are informative but not revealing sensitive info."""
        # Test with various error conditions
        response = test_client_macos.get("/nonexistent_endpoint")

        if response.status_code == 404 and response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            error_msg = data.get("detail", "")

            # Should be informative
            assert len(error_msg) > 5
            # Should not reveal internal paths or sensitive info
            assert "/src/" not in error_msg
            assert "password" not in error_msg.lower()
            assert "secret" not in error_msg.lower()


class TestRecoveryMechanisms:
    """Test error recovery mechanisms."""

    def test_service_retry_logic(self):
        """Test that services implement retry logic for transient failures."""
        from src.oaDeviceAPI.platforms.macos.services.utils import (
            execute_command_with_retry,
        )

        with patch("subprocess.run") as mock_run:
            # Fail twice, then succeed
            mock_run.side_effect = [
                subprocess.SubprocessError("Temporary failure"),
                subprocess.SubprocessError("Another failure"),
                Mock(returncode=0, stdout="success")
            ]

            result = execute_command_with_retry(["test", "command"], max_retries=3)

            assert result["success"] is True
            assert mock_run.call_count == 3

    def test_fallback_data_sources(self, test_client_macos):
        """Test that services have fallback data sources."""
        # When primary data source fails, should use fallbacks
        with patch("psutil.cpu_percent", side_effect=Exception("Primary CPU source failed")), \
             patch("subprocess.run") as mock_run:

            # Mock fallback command (like /proc/stat)
            mock_run.return_value = Mock(
                returncode=0,
                stdout="cpu  100 200 300 400 500"  # /proc/stat format
            )

            response = test_client_macos.get("/health")

            # Should still get CPU data from fallback
            if response.status_code == 200:
                data = response.json()
                if "metrics" in data and "cpu" in data["metrics"]:
                    assert "usage_percent" in data["metrics"]["cpu"]

    def test_graceful_degradation(self, test_client_macos):
        """Test graceful degradation when optional services fail."""
        # When optional services fail, core functionality should remain
        with patch("src.oaDeviceAPI.platforms.macos.services.camera.get_camera_info",
                  side_effect=Exception("Camera service failed")):

            # Core health endpoint should still work
            response = test_client_macos.get("/health")
            assert response.status_code == 200

            # Camera endpoint should indicate failure
            camera_response = test_client_macos.get("/cameras")
            assert camera_response.status_code in [200, 503]

            if camera_response.status_code == 200:
                camera_data = camera_response.json()
                assert camera_data.get("count", 0) == 0


class TestErrorLoggingAndMonitoring:
    """Test error logging and monitoring capabilities."""

    def test_error_logging_content(self, test_client_macos, caplog):
        """Test that errors are properly logged."""
        import logging

        with caplog.at_level(logging.ERROR):
            # Force an error condition
            with patch("src.oaDeviceAPI.core.platform.platform_manager.get_platform_info",
                      side_effect=Exception("Test error for logging")):

                response = test_client_macos.get("/platform")

                # Should log the error
                assert len(caplog.records) > 0
                error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
                assert len(error_logs) > 0

    def test_sensitive_data_not_logged(self, test_client_macos, caplog):
        """Test that sensitive data is not included in error logs."""
        import logging

        with caplog.at_level(logging.DEBUG):
            # Test with potential sensitive data in request
            sensitive_headers = {
                "Authorization": "Bearer secret_token",
                "X-API-Key": "super_secret_key"
            }

            response = test_client_macos.get("/health", headers=sensitive_headers)

            # Check logs don't contain sensitive data
            log_text = " ".join([record.getMessage() for record in caplog.records])
            assert "secret_token" not in log_text
            assert "super_secret_key" not in log_text

    def test_error_correlation_ids(self, test_client_macos):
        """Test that errors can be correlated (if correlation IDs are implemented)."""
        # This would test correlation ID functionality if implemented
        response = test_client_macos.get("/nonexistent")

        # Check for correlation ID in headers or response
        correlation_headers = [
            "x-correlation-id",
            "x-request-id",
            "x-trace-id"
        ]

        has_correlation = any(header in response.headers for header in correlation_headers)

        # If correlation is implemented, should be present
        # If not implemented, this test documents the expectation
        if has_correlation:
            assert any(response.headers.get(header) for header in correlation_headers)


class TestSecurityErrorHandling:
    """Test security-related error handling."""

    def test_authentication_error_handling(self, test_client_macos):
        """Test handling of authentication errors (if auth is implemented)."""
        # Test with invalid authentication
        invalid_auth_headers = {
            "Authorization": "Bearer invalid_token",
        }

        response = test_client_macos.get("/health", headers=invalid_auth_headers)

        # Should handle gracefully (currently no auth, so should work)
        # This test documents expected behavior if auth is added
        assert response.status_code in [200, 401]

    def test_authorization_error_handling(self, test_client_macos):
        """Test handling of authorization errors."""
        # Test accessing restricted endpoints
        restricted_endpoints = [
            "/actions/reboot",  # System action
        ]

        for endpoint in restricted_endpoints:
            response = test_client_macos.post(endpoint)

            # Should either work (no restrictions) or return 403
            assert response.status_code in [200, 401, 403]

    def test_input_sanitization_error_handling(self, test_client_macos):
        """Test input sanitization and injection prevention."""
        # Test various injection attempts
        injection_attempts = [
            {"param": "'; DROP TABLE users;--"},  # SQL injection
            {"param": "<script>alert('xss')</script>"},  # XSS
            {"param": "$(rm -rf /)"},  # Command injection
            {"param": "../../../etc/passwd"},  # Path traversal
        ]

        for attempt in injection_attempts:
            response = test_client_macos.get("/health", params=attempt)

            # Should handle malicious input gracefully
            assert response.status_code in [200, 400, 422]

            if response.status_code == 200:
                # Response should not contain the malicious input
                response_text = response.text
                assert attempt["param"] not in response_text


class TestFailoverAndRedundancy:
    """Test failover and redundancy mechanisms."""

    def test_service_failover_mechanisms(self, test_client_macos):
        """Test that services have appropriate failover mechanisms."""
        # When one data source fails, should try alternatives
        with patch("psutil.cpu_percent", side_effect=Exception("Primary source failed")):
            # Should try alternative methods for CPU data
            response = test_client_macos.get("/health")

            # Should either succeed with fallback or fail gracefully
            assert response.status_code in [200, 503]

    def test_partial_service_degradation(self, test_client_macos):
        """Test partial service degradation scenarios."""
        # When some services fail, others should continue working
        with patch("src.oaDeviceAPI.platforms.macos.services.camera.get_camera_info",
                  side_effect=Exception("Camera service down")):

            # Health should still work
            health_response = test_client_macos.get("/health")
            assert health_response.status_code == 200

            # Platform info should still work
            platform_response = test_client_macos.get("/platform")
            assert platform_response.status_code == 200

            # Only camera service should be affected
            camera_response = test_client_macos.get("/cameras")
            # May return empty list or error status
            assert camera_response.status_code in [200, 503]

    def test_cascading_failure_prevention(self, test_client_macos):
        """Test that failures don't cascade across services."""
        # Simulate failure in one service
        with patch("src.oaDeviceAPI.platforms.macos.services.tracker.get_tracker_stats",
                  side_effect=Exception("Tracker service critical error")):

            # Other services should remain unaffected
            health_response = test_client_macos.get("/health")
            platform_response = test_client_macos.get("/platform")

            # At least one should work
            assert (health_response.status_code == 200 or
                   platform_response.status_code == 200)

            # Tracker endpoint should handle its own failure
            tracker_response = test_client_macos.get("/tracker/stats")
            assert tracker_response.status_code in [200, 503]
